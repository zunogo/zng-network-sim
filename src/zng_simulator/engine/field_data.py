"""Field data integration — Phase 4 (§9).

CSV ingestion, variance analysis, and parameter auto-tuning:
  1. ``ingest_bms_csv``  — parse BMS telemetry into BMSRecord list
  2. ``ingest_charger_csv`` — parse charger failure logs
  3. ``compute_variance_report`` — projected vs actual for SOH and MTBF
  4. ``auto_tune_parameters`` — adjust model parameters from field observations
  5. ``check_charger_recommendation`` — flag when field data shifts NPV ranking

Ground-truth loop:
  Field CSV → FieldDataSet → variance_report → auto_tune → re-run sim → alert
"""

from __future__ import annotations

import csv
import io
import math
from copy import deepcopy
from pathlib import Path

import numpy as np

from zng_simulator.config.battery import PackSpec
from zng_simulator.config.charger import ChargerVariant
from zng_simulator.config.chaos import ChaosConfig
from zng_simulator.config.scenario import Scenario
from zng_simulator.config.station import StationConfig
from zng_simulator.models.field_data import (
    AutoTuneResult,
    BMSRecord,
    ChargerFailureRecord,
    ChargerRecommendationAlert,
    DegradationVariance,
    FieldDataSet,
    MTBFVariance,
    TunedParameter,
    VarianceReport,
)


# ═══════════════════════════════════════════════════════════════════════════
# CSV ingestion
# ═══════════════════════════════════════════════════════════════════════════

def ingest_bms_csv(source: str | Path | io.StringIO) -> list[BMSRecord]:
    """Parse a BMS telemetry CSV into a list of BMSRecord.

    Expected columns (header row required):
      pack_id, month, soh, cumulative_cycles[, temperature_avg_c]

    Parameters
    ----------
    source : str | Path | io.StringIO
        File path or in-memory StringIO with CSV content.

    Returns
    -------
    list[BMSRecord]
        Validated records.  Rows that fail validation are silently skipped.
    """
    rows = _read_csv(source)
    records: list[BMSRecord] = []
    for row in rows:
        try:
            rec = BMSRecord(
                pack_id=str(row["pack_id"]).strip(),
                month=int(row["month"]),
                soh=float(row["soh"]),
                cumulative_cycles=int(row["cumulative_cycles"]),
                temperature_avg_c=(
                    float(row["temperature_avg_c"])
                    if row.get("temperature_avg_c") not in (None, "", "NA", "null")
                    else None
                ),
            )
            records.append(rec)
        except (ValueError, KeyError, TypeError):
            continue  # skip malformed rows
    return records


def ingest_charger_csv(source: str | Path | io.StringIO) -> list[ChargerFailureRecord]:
    """Parse a charger failure log CSV into ChargerFailureRecord list.

    Expected columns (header row required):
      dock_id, failure_month, downtime_hours[, charger_variant_name, repair_cost, was_replaced]

    Parameters
    ----------
    source : str | Path | io.StringIO
        File path or in-memory StringIO with CSV content.

    Returns
    -------
    list[ChargerFailureRecord]
        Validated records.
    """
    rows = _read_csv(source)
    records: list[ChargerFailureRecord] = []
    for row in rows:
        try:
            rec = ChargerFailureRecord(
                dock_id=str(row["dock_id"]).strip(),
                charger_variant_name=(
                    str(row["charger_variant_name"]).strip()
                    if row.get("charger_variant_name") not in (None, "", "NA", "null")
                    else None
                ),
                failure_month=int(row["failure_month"]),
                downtime_hours=float(row["downtime_hours"]),
                repair_cost=(
                    float(row["repair_cost"])
                    if row.get("repair_cost") not in (None, "", "NA", "null")
                    else None
                ),
                was_replaced=(
                    str(row.get("was_replaced", "")).strip().lower()
                    in ("true", "1", "yes")
                ),
            )
            records.append(rec)
        except (ValueError, KeyError, TypeError):
            continue
    return records


def _read_csv(source: str | Path | io.StringIO) -> list[dict[str, str]]:
    """Read CSV from file path or StringIO, returning list of dicts."""
    if isinstance(source, io.StringIO):
        source.seek(0)
        reader = csv.DictReader(source)
        return list(reader)
    path = Path(source)
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


# ═══════════════════════════════════════════════════════════════════════════
# Variance analysis
# ═══════════════════════════════════════════════════════════════════════════

def compute_variance_report(
    field_data: FieldDataSet,
    pack: PackSpec,
    charger: ChargerVariant,
    chaos: ChaosConfig | None = None,
    station: StationConfig | None = None,
) -> VarianceReport:
    """Compare projected model values against field observations.

    Degradation variance:
      For each month in the field data, compute the model-predicted SOH
      and compare against the actual measured average SOH.

    MTBF variance:
      Compute actual MTBF = total_operating_hours / total_failures
      and compare against the charger spec MTBF.

    Parameters
    ----------
    field_data : FieldDataSet
        Ingested BMS and charger failure data.
    pack : PackSpec
        Pack config (for degradation model β, calendar aging).
    charger : ChargerVariant
        Charger config (for MTBF spec value).
    chaos : ChaosConfig | None
        Chaos config (aggressiveness index for degradation model).
    station : StationConfig | None
        Station config (for operating hours when computing actual MTBF).
    """
    deg_monthly = _compute_degradation_variance(field_data, pack, chaos)
    mtbf_list = _compute_mtbf_variance(field_data, charger, station)

    # Overall drift summaries
    overall_soh_drift = None
    if deg_monthly:
        overall_soh_drift = sum(d.variance_pct for d in deg_monthly) / len(deg_monthly)

    overall_mtbf_drift = None
    if mtbf_list:
        overall_mtbf_drift = sum(m.variance_pct for m in mtbf_list) / len(mtbf_list)

    return VarianceReport(
        degradation_monthly=deg_monthly,
        mtbf_variance=mtbf_list,
        overall_soh_drift_pct=(
            round(overall_soh_drift, 4) if overall_soh_drift is not None else None
        ),
        overall_mtbf_drift_pct=(
            round(overall_mtbf_drift, 4) if overall_mtbf_drift is not None else None
        ),
    )


def _compute_degradation_variance(
    field_data: FieldDataSet,
    pack: PackSpec,
    chaos: ChaosConfig | None,
) -> list[DegradationVariance]:
    """Month-by-month SOH variance: model prediction vs field average."""
    if not field_data.bms_records:
        return []

    aggressiveness = chaos.aggressiveness_index if chaos else 1.0
    beta_per_cycle = (pack.cycle_degradation_rate_pct / 100.0) * aggressiveness
    calendar_per_month = pack.calendar_aging_rate_pct_per_month / 100.0

    # Group field records by month → compute actual avg SOH
    months_data: dict[int, list[BMSRecord]] = {}
    for rec in field_data.bms_records:
        months_data.setdefault(rec.month, []).append(rec)

    # Compute average cycles per pack at each month for model projection
    # Use the field data's cumulative cycles to determine how many cycles
    # each pack has done, so the model projection matches the actual usage.
    results: list[DegradationVariance] = []

    for month in sorted(months_data.keys()):
        records = months_data[month]
        actual_avg_soh = sum(r.soh for r in records) / len(records)
        avg_cumulative_cycles = sum(r.cumulative_cycles for r in records) / len(records)

        # Model prediction: SOH = 1.0 - β × cycles - calendar × months
        projected_soh_loss_cycling = beta_per_cycle * avg_cumulative_cycles
        projected_soh_loss_calendar = calendar_per_month * month
        projected_avg_soh = max(1.0 - projected_soh_loss_cycling - projected_soh_loss_calendar, 0.0)

        variance_pct = (
            (actual_avg_soh - projected_avg_soh) / projected_avg_soh * 100.0
            if projected_avg_soh > 0 else 0.0
        )

        results.append(DegradationVariance(
            month=month,
            projected_avg_soh=round(projected_avg_soh, 6),
            actual_avg_soh=round(actual_avg_soh, 6),
            variance_pct=round(variance_pct, 4),
            num_packs_sampled=len(records),
        ))

    return results


def _compute_mtbf_variance(
    field_data: FieldDataSet,
    charger: ChargerVariant,
    station: StationConfig | None,
) -> list[MTBFVariance]:
    """Compute actual MTBF from field failure data vs charger spec."""
    if not field_data.charger_failure_records:
        return []

    # Group failures by charger variant (or aggregate if no variant info)
    variants: dict[str | None, list[ChargerFailureRecord]] = {}
    for rec in field_data.charger_failure_records:
        key = rec.charger_variant_name
        variants.setdefault(key, []).append(rec)

    operating_hours_per_day = station.operating_hours_per_day if station else 18.0

    results: list[MTBFVariance] = []

    for variant_name, failures in variants.items():
        total_failures = len(failures)
        if total_failures == 0:
            continue

        # Estimate total operating hours from the span of data
        max_month = max(f.failure_month for f in failures)
        num_unique_docks = len({f.dock_id for f in failures})

        # Total fleet operating hours = docks × hours/day × 30 days × months
        total_operating_hours = num_unique_docks * operating_hours_per_day * 30 * max_month

        # Actual MTBF = total operating hours / total failures
        actual_mtbf = total_operating_hours / total_failures if total_failures > 0 else float("inf")

        projected_mtbf = charger.mtbf_hours
        variance_pct = (
            (actual_mtbf - projected_mtbf) / projected_mtbf * 100.0
            if projected_mtbf > 0 else 0.0
        )

        results.append(MTBFVariance(
            charger_variant_name=variant_name,
            projected_mtbf_hours=projected_mtbf,
            actual_mtbf_hours=round(actual_mtbf, 2),
            variance_pct=round(variance_pct, 4),
            total_operating_hours=round(total_operating_hours, 2),
            total_failures=total_failures,
        ))

    return results


# ═══════════════════════════════════════════════════════════════════════════
# Auto-tuning
# ═══════════════════════════════════════════════════════════════════════════

def auto_tune_parameters(
    field_data: FieldDataSet,
    scenario: Scenario,
    charger: ChargerVariant,
    min_confidence: float = 0.5,
) -> AutoTuneResult:
    """Adjust model parameters based on field observations.

    Currently tunes:
      1. ``pack.cycle_degradation_rate_pct`` — from field SOH trajectory
      2. ``charger.mtbf_hours`` — from field failure frequency

    Confidence is based on sample size:
      - BMS: confidence = min(1.0, num_packs / 50)  (50+ packs = full confidence)
      - MTBF: confidence = min(1.0, num_failures / 10)  (10+ failures = full confidence)

    Parameters with confidence < min_confidence are excluded.

    Parameters
    ----------
    field_data : FieldDataSet
        Ingested field data.
    scenario : Scenario
        Current scenario config.
    charger : ChargerVariant
        Charger variant being evaluated.
    min_confidence : float
        Minimum confidence threshold (0–1) to include a tuned parameter.

    Returns
    -------
    AutoTuneResult
        Tuned parameters with original and new values.
    """
    tuned: list[TunedParameter] = []

    # --- 1. Tune degradation rate β from BMS data ---
    tuned_beta = _tune_degradation_rate(field_data, scenario.pack, scenario.chaos)
    if tuned_beta is not None:
        confidence = min(1.0, field_data.num_unique_packs / 50)
        if confidence >= min_confidence:
            original = scenario.pack.cycle_degradation_rate_pct
            change_pct = (tuned_beta - original) / original * 100 if original > 0 else 0
            tuned.append(TunedParameter(
                param_path="pack.cycle_degradation_rate_pct",
                original_value=original,
                tuned_value=round(tuned_beta, 6),
                change_pct=round(change_pct, 2),
                confidence=round(confidence, 2),
            ))

    # --- 2. Tune charger MTBF from failure logs ---
    tuned_mtbf = _tune_charger_mtbf(field_data, charger, scenario.station)
    if tuned_mtbf is not None:
        num_failures = len(field_data.charger_failure_records)
        confidence = min(1.0, num_failures / 10)
        if confidence >= min_confidence:
            original = charger.mtbf_hours
            change_pct = (tuned_mtbf - original) / original * 100 if original > 0 else 0
            tuned.append(TunedParameter(
                param_path="charger.mtbf_hours",
                original_value=original,
                tuned_value=round(tuned_mtbf, 2),
                change_pct=round(change_pct, 2),
                confidence=round(confidence, 2),
            ))

    # --- 3. Tune calendar aging from BMS data ---
    tuned_calendar = _tune_calendar_aging(field_data, scenario.pack, scenario.chaos)
    if tuned_calendar is not None:
        confidence = min(1.0, field_data.num_unique_packs / 50)
        if confidence >= min_confidence:
            original = scenario.pack.calendar_aging_rate_pct_per_month
            change_pct = (tuned_calendar - original) / original * 100 if original > 0 else 0
            tuned.append(TunedParameter(
                param_path="pack.calendar_aging_rate_pct_per_month",
                original_value=original,
                tuned_value=round(tuned_calendar, 6),
                change_pct=round(change_pct, 2),
                confidence=round(confidence, 2),
            ))

    return AutoTuneResult(
        parameters=tuned,
        data_months_used=field_data.max_month,
        num_packs_used=field_data.num_unique_packs,
        num_failure_events_used=len(field_data.charger_failure_records),
    )


def _tune_degradation_rate(
    field_data: FieldDataSet,
    pack: PackSpec,
    chaos: ChaosConfig | None,
) -> float | None:
    """Estimate β (cycle_degradation_rate_pct) from field SOH data.

    Uses a simple linear regression approach:
      SOH = 1.0 - β_eff × cycles - calendar × months
      → β_eff = (1.0 - SOH - calendar × months) / cycles
      → β_pct = β_eff / aggressiveness × 100

    Returns the mean β across all observations, or None if insufficient data.
    """
    if not field_data.bms_records:
        return None

    aggressiveness = chaos.aggressiveness_index if chaos else 1.0
    calendar_per_month = pack.calendar_aging_rate_pct_per_month / 100.0

    betas: list[float] = []
    for rec in field_data.bms_records:
        if rec.cumulative_cycles <= 0:
            continue
        # SOH loss from calendar aging over rec.month months
        calendar_loss = calendar_per_month * rec.month
        # Remaining SOH loss attributable to cycling
        cycling_loss = 1.0 - rec.soh - calendar_loss
        if cycling_loss < 0:
            # Calendar aging alone exceeds observed loss — β ≈ 0 or data anomaly
            cycling_loss = 0.0
        # β_eff = cycling_loss / cycles
        beta_eff = cycling_loss / rec.cumulative_cycles
        # Remove aggressiveness to get the raw β
        beta_raw = beta_eff / aggressiveness if aggressiveness > 0 else beta_eff
        betas.append(beta_raw * 100.0)  # convert to pct

    if not betas:
        return None

    return float(np.median(betas))


def _tune_calendar_aging(
    field_data: FieldDataSet,
    pack: PackSpec,
    chaos: ChaosConfig | None,
) -> float | None:
    """Estimate calendar aging rate from field data.

    For packs with very low cycle counts (< 50 cumulative), most SOH loss
    is from calendar aging.  Estimate: calendar_rate = (1.0 - SOH) / months.
    """
    if not field_data.bms_records:
        return None

    # Use low-cycle packs (< 50 cycles) for calendar aging estimation
    low_cycle_records = [r for r in field_data.bms_records if r.cumulative_cycles < 50 and r.month > 0]
    if len(low_cycle_records) < 3:
        return None  # Insufficient data

    rates: list[float] = []
    for rec in low_cycle_records:
        soh_loss = 1.0 - rec.soh
        if soh_loss <= 0:
            continue
        monthly_rate = soh_loss / rec.month
        rates.append(monthly_rate * 100.0)  # convert to pct

    if not rates:
        return None

    return float(np.median(rates))


def _tune_charger_mtbf(
    field_data: FieldDataSet,
    charger: ChargerVariant,
    station: StationConfig | None,
) -> float | None:
    """Estimate actual MTBF from charger failure log data.

    actual_MTBF = total_operating_hours / total_failures
    """
    if not field_data.charger_failure_records:
        return None

    operating_hours_per_day = station.operating_hours_per_day if station else 18.0
    failures = field_data.charger_failure_records
    total_failures = len(failures)
    if total_failures == 0:
        return None

    max_month = max(f.failure_month for f in failures)
    num_unique_docks = len({f.dock_id for f in failures})

    total_operating_hours = num_unique_docks * operating_hours_per_day * 30 * max_month
    actual_mtbf = total_operating_hours / total_failures

    return actual_mtbf


# ═══════════════════════════════════════════════════════════════════════════
# Charger recommendation alerts
# ═══════════════════════════════════════════════════════════════════════════

def check_charger_recommendation(
    scenario: Scenario,
    charger_variants: list[ChargerVariant],
    auto_tune_results: dict[str, AutoTuneResult],
    original_npvs: dict[str, float],
    threshold_pct: float = 10.0,
) -> list[ChargerRecommendationAlert]:
    """Check whether field-tuned parameters change the charger NPV ranking.

    Parameters
    ----------
    scenario : Scenario
        Current scenario config.
    charger_variants : list[ChargerVariant]
        All charger variants being compared.
    auto_tune_results : dict[str, AutoTuneResult]
        Auto-tune results keyed by charger variant name.
    original_npvs : dict[str, float]
        NPV per charger variant under original (spec) parameters.
    threshold_pct : float
        Minimum NPV change (%) to trigger an alert.

    Returns
    -------
    list[ChargerRecommendationAlert]
        Alerts for chargers where field data materially changes the recommendation.
    """
    from zng_simulator.engine.orchestrator import run_engine
    from zng_simulator.finance.dcf import build_dcf_table

    alerts: list[ChargerRecommendationAlert] = []

    for charger in charger_variants:
        tune_result = auto_tune_results.get(charger.name)
        if not tune_result or not tune_result.parameters:
            continue

        # Apply tuned parameters to scenario + charger
        tuned_scenario = deepcopy(scenario)
        tuned_charger = deepcopy(charger)

        for param in tune_result.parameters:
            if param.param_path.startswith("charger."):
                attr_name = param.param_path.split(".", 1)[1]
                setattr(tuned_charger, attr_name, param.tuned_value)
            else:
                _set_nested(tuned_scenario, param.param_path, param.tuned_value)

        # Force static engine for speed
        tuned_scenario.simulation.engine = "static"

        # Re-run simulation with tuned parameters
        result = run_engine(tuned_scenario, tuned_charger)
        salvage = result.derived.total_packs * tuned_scenario.pack.second_life_salvage_value
        dcf = build_dcf_table(
            result.months, result.summary, tuned_scenario.finance,
            tuned_scenario.simulation.discount_rate_annual, salvage,
        )
        revised_npv = dcf.npv

        original_npv = original_npvs.get(charger.name, 0.0)
        npv_delta = revised_npv - original_npv
        change_pct = abs(npv_delta / original_npv * 100) if original_npv != 0 else 0

        if change_pct >= threshold_pct:
            # Determine severity
            if change_pct >= 30:
                severity = "critical"
            elif change_pct >= 15:
                severity = "warning"
            else:
                severity = "info"

            # Build message
            direction = "worse" if npv_delta < 0 else "better"
            param_changes = ", ".join(
                f"{p.param_path}: {p.original_value:.4g} → {p.tuned_value:.4g} ({p.change_pct:+.1f}%)"
                for p in tune_result.parameters
            )
            message = (
                f"Field data shows {charger.name} performing {direction} than spec. "
                f"NPV changed by ₹{npv_delta:,.0f} ({change_pct:+.1f}%). "
                f"Parameter changes: {param_changes}"
            )

            alerts.append(ChargerRecommendationAlert(
                alert_type="mtbf_drift" if any("mtbf" in p.param_path for p in tune_result.parameters) else "cost_overrun",
                severity=severity,
                message=message,
                affected_charger=charger.name,
                original_npv=round(original_npv, 2),
                revised_npv=round(revised_npv, 2),
                npv_delta=round(npv_delta, 2),
            ))

    # Check for ranking change
    if len(original_npvs) >= 2 and len(alerts) >= 1:
        # Original ranking
        orig_ranking = sorted(original_npvs.items(), key=lambda x: x[1], reverse=True)
        orig_best = orig_ranking[0][0]

        # Revised NPVs (from alerts)
        revised_npvs = dict(original_npvs)
        for alert in alerts:
            if alert.affected_charger and alert.revised_npv is not None:
                revised_npvs[alert.affected_charger] = alert.revised_npv

        new_ranking = sorted(revised_npvs.items(), key=lambda x: x[1], reverse=True)
        new_best = new_ranking[0][0]

        if new_best != orig_best:
            alerts.append(ChargerRecommendationAlert(
                alert_type="ranking_change",
                severity="critical",
                message=(
                    f"Charger recommendation changed! "
                    f"Original best: {orig_best}. "
                    f"Field-data-adjusted best: {new_best}."
                ),
                affected_charger=new_best,
            ))

    return alerts


def _set_nested(obj: object, path: str, value: float) -> None:
    """Set a nested attribute via dot-path string."""
    parts = path.split(".")
    current = obj
    for part in parts[:-1]:
        current = getattr(current, part)
    setattr(current, parts[-1], value)


def apply_tuned_parameters(
    scenario: Scenario,
    charger: ChargerVariant,
    tune_result: AutoTuneResult,
) -> tuple[Scenario, ChargerVariant]:
    """Apply tuned parameters to scenario and charger (returns copies).

    Parameters
    ----------
    scenario : Scenario
        Original scenario.
    charger : ChargerVariant
        Original charger variant.
    tune_result : AutoTuneResult
        Auto-tune output containing tuned parameters.

    Returns
    -------
    tuple[Scenario, ChargerVariant]
        Deep copies with tuned values applied.
    """
    tuned_scenario = deepcopy(scenario)
    tuned_charger = deepcopy(charger)

    for param in tune_result.parameters:
        if param.param_path.startswith("charger."):
            attr_name = param.param_path.split(".", 1)[1]
            setattr(tuned_charger, attr_name, param.tuned_value)
        else:
            _set_nested(tuned_scenario, param.param_path, param.tuned_value)

    return tuned_scenario, tuned_charger
