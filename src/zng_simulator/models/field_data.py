"""Phase 4 result types — field data, variance analysis, pilot sizing (§9 + §7.2).

Models for:
  - Ingested field data (BMS telemetry rows, charger failure log rows)
  - Variance analysis results (projected vs actual for SOH and MTBF)
  - Auto-tuning output (updated parameter estimates from field data)
  - Pilot sizing / optimizer results
  - Charger recommendation alerts (when field data shifts the NPV ranking)
"""

from __future__ import annotations

from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════════════════════════════
# Field data records (ingested from CSVs)
# ═══════════════════════════════════════════════════════════════════════════

class BMSRecord(BaseModel):
    """One row from a BMS telemetry CSV.

    Minimal columns required for variance analysis:
      pack_id, month, soh, cumulative_cycles
    """

    pack_id: str
    """Unique identifier for the physical pack."""

    month: int = Field(ge=1)
    """Month number (1-indexed, relative to deployment start)."""

    soh: float = Field(ge=0, le=1.0)
    """Measured state-of-health at this reading (0–1)."""

    cumulative_cycles: int = Field(ge=0)
    """Total charge-discharge cycles recorded up to this reading."""

    temperature_avg_c: float | None = None
    """Average ambient temperature during this period (°C). Optional."""


class ChargerFailureRecord(BaseModel):
    """One row from a charger failure log CSV.

    Minimal columns: dock_id, failure_month, downtime_hours
    """

    dock_id: str
    """Identifier for the charger slot that failed."""

    charger_variant_name: str | None = None
    """Which charger variant this dock belongs to. Optional (for multi-variant fleets)."""

    failure_month: int = Field(ge=1)
    """Month in which the failure occurred (1-indexed)."""

    downtime_hours: float = Field(ge=0)
    """Actual hours of downtime for this failure event."""

    repair_cost: float | None = None
    """Actual repair cost (₹) if recorded. Optional."""

    was_replaced: bool = False
    """True if this failure led to a full unit replacement."""


class FieldDataSet(BaseModel):
    """Container for all ingested field data."""

    bms_records: list[BMSRecord] = Field(default_factory=list)
    charger_failure_records: list[ChargerFailureRecord] = Field(default_factory=list)

    @property
    def num_unique_packs(self) -> int:
        return len({r.pack_id for r in self.bms_records})

    @property
    def num_unique_docks(self) -> int:
        return len({r.dock_id for r in self.charger_failure_records})

    @property
    def max_month(self) -> int:
        months: list[int] = []
        if self.bms_records:
            months.append(max(r.month for r in self.bms_records))
        if self.charger_failure_records:
            months.append(max(r.failure_month for r in self.charger_failure_records))
        return max(months) if months else 0


# ═══════════════════════════════════════════════════════════════════════════
# Variance analysis results
# ═══════════════════════════════════════════════════════════════════════════

class DegradationVariance(BaseModel):
    """Projected vs actual battery degradation comparison."""

    month: int
    projected_avg_soh: float
    """Model-predicted average SOH at this month."""

    actual_avg_soh: float
    """Field-measured average SOH at this month."""

    variance_pct: float
    """(actual − projected) / projected × 100.  Negative = degrading faster."""

    num_packs_sampled: int
    """Number of packs with field data at this month."""


class MTBFVariance(BaseModel):
    """Projected vs actual charger MTBF comparison."""

    charger_variant_name: str | None = None
    """Charger variant (None = fleet-wide aggregate)."""

    projected_mtbf_hours: float
    """MTBF from charger spec (input parameter)."""

    actual_mtbf_hours: float
    """MTBF computed from field failure data."""

    variance_pct: float
    """(actual − projected) / projected × 100.  Negative = failing more often."""

    total_operating_hours: float
    """Total dock-hours observed in field data."""

    total_failures: int
    """Total failure events observed."""


class VarianceReport(BaseModel):
    """Complete variance analysis: projected vs actual for degradation and MTBF."""

    degradation_monthly: list[DegradationVariance] = Field(default_factory=list)
    """Month-by-month SOH variance."""

    mtbf_variance: list[MTBFVariance] = Field(default_factory=list)
    """Per-variant (or aggregate) MTBF variance."""

    overall_soh_drift_pct: float | None = None
    """Fleet-average SOH drift across all months (negative = faster degradation)."""

    overall_mtbf_drift_pct: float | None = None
    """Fleet-average MTBF drift (negative = more failures than predicted)."""


# ═══════════════════════════════════════════════════════════════════════════
# Auto-tuning results
# ═══════════════════════════════════════════════════════════════════════════

class TunedParameter(BaseModel):
    """One parameter that was adjusted by auto-tuning."""

    param_path: str
    """Dot-path into Scenario config (e.g. 'pack.cycle_degradation_rate_pct')."""

    original_value: float
    """Value before tuning (from the scenario config)."""

    tuned_value: float
    """Value after tuning (from field data)."""

    change_pct: float
    """(tuned − original) / original × 100."""

    confidence: float = Field(ge=0, le=1.0)
    """Confidence in the tuned value (0–1). Based on sample size / data quality."""


class AutoTuneResult(BaseModel):
    """Output of the parameter auto-tuning process."""

    parameters: list[TunedParameter] = Field(default_factory=list)
    """List of parameters that were adjusted."""

    data_months_used: int
    """Number of months of field data used for tuning."""

    num_packs_used: int
    """Number of unique packs in the BMS data set."""

    num_failure_events_used: int
    """Number of charger failure events used."""


# ═══════════════════════════════════════════════════════════════════════════
# Charger recommendation alert
# ═══════════════════════════════════════════════════════════════════════════

class ChargerRecommendationAlert(BaseModel):
    """Raised when field data materially changes a charger recommendation.

    Example: "Field MTBF of Budget charger is 40% below spec —
             Premium charger is now NPV-positive to switch to."
    """

    alert_type: str
    """Category: 'mtbf_drift', 'ranking_change', 'cost_overrun'."""

    severity: str
    """'info', 'warning', 'critical'."""

    message: str
    """Human-readable alert message."""

    affected_charger: str
    """Name of the charger variant affected."""

    original_npv: float | None = None
    """NPV under original (spec) parameters."""

    revised_npv: float | None = None
    """NPV under field-tuned parameters."""

    npv_delta: float | None = None
    """Change in NPV due to field data."""


# ═══════════════════════════════════════════════════════════════════════════
# Pilot sizing / optimizer results
# ═══════════════════════════════════════════════════════════════════════════

class PilotSizingResult(BaseModel):
    """Output of the pilot sizing optimizer.

    Answers: "What is the minimum fleet size / station count to achieve
    positive operating cash flow under the specified confidence level?"
    """

    recommended_fleet_size: int
    """Minimum fleet size (vehicles) to hit target."""

    recommended_num_stations: int
    """Number of stations (may stay fixed or be part of the search)."""

    recommended_docks_per_station: int
    """Docks per station at recommended scale."""

    target_confidence_pct: float
    """Confidence level used (e.g. 50 = median, 90 = P90)."""

    target_metric: str
    """What was optimized for: 'positive_ncf', 'positive_npv', 'break_even_within'."""

    achieved: bool
    """Whether the target was achievable within search bounds."""

    best_npv: float | None = None
    """NPV at the recommended scale (under stochastic engine)."""

    best_break_even_month: int | None = None
    """Break-even month at the recommended scale."""

    best_monthly_ncf_at_target: float | None = None
    """Steady-state monthly NCF at the recommended scale."""

    search_iterations: int = 0
    """Number of engine runs performed during the search."""

    search_log: list[dict] = Field(default_factory=list)
    """Log of (fleet_size, npv, break_even) at each search step."""
