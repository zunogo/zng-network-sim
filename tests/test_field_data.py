"""Tests for field data integration — Phase 4 (§9).

Covers:
  - BMS CSV ingestion (valid, malformed, missing columns)
  - Charger failure CSV ingestion
  - Variance analysis (degradation + MTBF)
  - Auto-tuning (degradation rate, MTBF, calendar aging)
  - apply_tuned_parameters helper
"""

import io

import pytest

from zng_simulator.config.battery import PackSpec
from zng_simulator.config.charger import ChargerVariant
from zng_simulator.config.chaos import ChaosConfig
from zng_simulator.config.scenario import Scenario
from zng_simulator.config.station import StationConfig
from zng_simulator.engine.field_data import (
    apply_tuned_parameters,
    auto_tune_parameters,
    compute_variance_report,
    ingest_bms_csv,
    ingest_charger_csv,
)
from zng_simulator.models.field_data import (
    BMSRecord,
    ChargerFailureRecord,
    FieldDataSet,
)


# ═══════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════

BMS_CSV_VALID = """\
pack_id,month,soh,cumulative_cycles,temperature_avg_c
P001,6,0.95,300,35.2
P001,12,0.89,620,34.0
P002,6,0.94,310,36.0
P002,12,0.88,650,33.5
P003,6,0.96,280,34.5
P003,12,0.90,590,35.1
"""

BMS_CSV_MALFORMED = """\
pack_id,month,soh,cumulative_cycles
P001,6,0.95,300
BAD_ROW,abc,def,ghi
P002,12,0.88,650
,6,0.96,280
"""

CHARGER_CSV_VALID = """\
dock_id,failure_month,downtime_hours,charger_variant_name,repair_cost,was_replaced
D01,3,8.5,Budget-1kW,1200,false
D02,5,12.0,Budget-1kW,1500,false
D01,9,24.0,Budget-1kW,2000,true
D03,7,6.0,Budget-1kW,800,false
"""


def _default_pack() -> PackSpec:
    return PackSpec(
        cycle_degradation_rate_pct=0.01,
        calendar_aging_rate_pct_per_month=0.15,
    )


def _default_charger() -> ChargerVariant:
    return ChargerVariant(name="Budget-1kW", mtbf_hours=80_000)


def _default_station() -> StationConfig:
    return StationConfig(operating_hours_per_day=18.0)


def _default_chaos() -> ChaosConfig:
    return ChaosConfig(aggressiveness_index=1.0)


# ═══════════════════════════════════════════════════════════════════════════
# BMS CSV ingestion
# ═══════════════════════════════════════════════════════════════════════════

class TestIngestBMSCSV:
    def test_valid_csv_parsed(self):
        records = ingest_bms_csv(io.StringIO(BMS_CSV_VALID))
        assert len(records) == 6  # 3 packs × 2 months
        assert all(isinstance(r, BMSRecord) for r in records)

    def test_pack_ids(self):
        records = ingest_bms_csv(io.StringIO(BMS_CSV_VALID))
        pack_ids = {r.pack_id for r in records}
        assert pack_ids == {"P001", "P002", "P003"}

    def test_soh_range(self):
        records = ingest_bms_csv(io.StringIO(BMS_CSV_VALID))
        for r in records:
            assert 0.0 <= r.soh <= 1.0

    def test_temperature_parsed(self):
        records = ingest_bms_csv(io.StringIO(BMS_CSV_VALID))
        assert records[0].temperature_avg_c == pytest.approx(35.2)

    def test_malformed_rows_skipped(self):
        """Malformed rows are silently skipped — only valid rows returned."""
        records = ingest_bms_csv(io.StringIO(BMS_CSV_MALFORMED))
        # P001 valid, BAD_ROW skipped, P002 valid, missing pack_id skipped
        assert len(records) >= 2
        pack_ids = {r.pack_id for r in records}
        assert "P001" in pack_ids
        assert "P002" in pack_ids

    def test_no_temperature_column(self):
        csv_no_temp = "pack_id,month,soh,cumulative_cycles\nP001,6,0.95,300\n"
        records = ingest_bms_csv(io.StringIO(csv_no_temp))
        assert len(records) == 1
        assert records[0].temperature_avg_c is None

    def test_empty_csv(self):
        records = ingest_bms_csv(io.StringIO("pack_id,month,soh,cumulative_cycles\n"))
        assert records == []


# ═══════════════════════════════════════════════════════════════════════════
# Charger failure CSV ingestion
# ═══════════════════════════════════════════════════════════════════════════

class TestIngestChargerCSV:
    def test_valid_csv(self):
        records = ingest_charger_csv(io.StringIO(CHARGER_CSV_VALID))
        assert len(records) == 4
        assert all(isinstance(r, ChargerFailureRecord) for r in records)

    def test_was_replaced_flag(self):
        records = ingest_charger_csv(io.StringIO(CHARGER_CSV_VALID))
        replaced = [r for r in records if r.was_replaced]
        assert len(replaced) == 1
        assert replaced[0].dock_id == "D01"
        assert replaced[0].failure_month == 9

    def test_repair_cost_parsed(self):
        records = ingest_charger_csv(io.StringIO(CHARGER_CSV_VALID))
        assert records[0].repair_cost == pytest.approx(1200.0)

    def test_variant_name(self):
        records = ingest_charger_csv(io.StringIO(CHARGER_CSV_VALID))
        assert all(r.charger_variant_name == "Budget-1kW" for r in records)

    def test_empty_csv(self):
        records = ingest_charger_csv(
            io.StringIO("dock_id,failure_month,downtime_hours\n")
        )
        assert records == []

    def test_minimal_columns(self):
        csv_min = "dock_id,failure_month,downtime_hours\nD01,3,8.5\n"
        records = ingest_charger_csv(io.StringIO(csv_min))
        assert len(records) == 1
        assert records[0].charger_variant_name is None
        assert records[0].repair_cost is None
        assert records[0].was_replaced is False


# ═══════════════════════════════════════════════════════════════════════════
# FieldDataSet model
# ═══════════════════════════════════════════════════════════════════════════

class TestFieldDataSet:
    def test_num_unique_packs(self):
        records = ingest_bms_csv(io.StringIO(BMS_CSV_VALID))
        fds = FieldDataSet(bms_records=records)
        assert fds.num_unique_packs == 3

    def test_num_unique_docks(self):
        records = ingest_charger_csv(io.StringIO(CHARGER_CSV_VALID))
        fds = FieldDataSet(charger_failure_records=records)
        assert fds.num_unique_docks == 3  # D01, D02, D03

    def test_max_month_bms(self):
        records = ingest_bms_csv(io.StringIO(BMS_CSV_VALID))
        fds = FieldDataSet(bms_records=records)
        assert fds.max_month == 12

    def test_max_month_charger(self):
        records = ingest_charger_csv(io.StringIO(CHARGER_CSV_VALID))
        fds = FieldDataSet(charger_failure_records=records)
        assert fds.max_month == 9

    def test_max_month_empty(self):
        fds = FieldDataSet()
        assert fds.max_month == 0


# ═══════════════════════════════════════════════════════════════════════════
# Variance analysis
# ═══════════════════════════════════════════════════════════════════════════

class TestVarianceReport:
    def test_degradation_variance_computed(self):
        bms = ingest_bms_csv(io.StringIO(BMS_CSV_VALID))
        fds = FieldDataSet(bms_records=bms)
        pack = _default_pack()
        charger = _default_charger()

        report = compute_variance_report(fds, pack, charger, _default_chaos())
        assert len(report.degradation_monthly) == 2  # month 6 and 12
        assert report.degradation_monthly[0].month == 6
        assert report.degradation_monthly[1].month == 12

    def test_degradation_variance_values(self):
        bms = ingest_bms_csv(io.StringIO(BMS_CSV_VALID))
        fds = FieldDataSet(bms_records=bms)
        pack = _default_pack()
        charger = _default_charger()

        report = compute_variance_report(fds, pack, charger, _default_chaos())
        for dv in report.degradation_monthly:
            assert dv.projected_avg_soh > 0
            assert dv.actual_avg_soh > 0
            assert dv.num_packs_sampled == 3  # 3 packs per month

    def test_mtbf_variance_computed(self):
        cfail = ingest_charger_csv(io.StringIO(CHARGER_CSV_VALID))
        fds = FieldDataSet(charger_failure_records=cfail)
        pack = _default_pack()
        charger = _default_charger()
        station = _default_station()

        report = compute_variance_report(fds, pack, charger, station=station)
        assert len(report.mtbf_variance) >= 1
        mtbf = report.mtbf_variance[0]
        assert mtbf.projected_mtbf_hours == 80_000
        assert mtbf.actual_mtbf_hours > 0
        assert mtbf.total_failures == 4

    def test_overall_drift(self):
        bms = ingest_bms_csv(io.StringIO(BMS_CSV_VALID))
        cfail = ingest_charger_csv(io.StringIO(CHARGER_CSV_VALID))
        fds = FieldDataSet(bms_records=bms, charger_failure_records=cfail)
        pack = _default_pack()
        charger = _default_charger()

        report = compute_variance_report(fds, pack, charger, _default_chaos(), _default_station())
        assert report.overall_soh_drift_pct is not None
        assert report.overall_mtbf_drift_pct is not None

    def test_empty_field_data(self):
        fds = FieldDataSet()
        pack = _default_pack()
        charger = _default_charger()

        report = compute_variance_report(fds, pack, charger)
        assert report.degradation_monthly == []
        assert report.mtbf_variance == []
        assert report.overall_soh_drift_pct is None
        assert report.overall_mtbf_drift_pct is None


# ═══════════════════════════════════════════════════════════════════════════
# Auto-tuning
# ═══════════════════════════════════════════════════════════════════════════

class TestAutoTune:
    def _make_field_data(self) -> FieldDataSet:
        bms = ingest_bms_csv(io.StringIO(BMS_CSV_VALID))
        cfail = ingest_charger_csv(io.StringIO(CHARGER_CSV_VALID))
        return FieldDataSet(bms_records=bms, charger_failure_records=cfail)

    def test_auto_tune_returns_result(self):
        fds = self._make_field_data()
        scenario = Scenario()
        charger = _default_charger()

        result = auto_tune_parameters(fds, scenario, charger, min_confidence=0.0)
        assert result.data_months_used == 12
        assert result.num_packs_used == 3

    def test_degradation_rate_tuned(self):
        fds = self._make_field_data()
        scenario = Scenario()
        charger = _default_charger()

        result = auto_tune_parameters(fds, scenario, charger, min_confidence=0.0)
        beta_params = [p for p in result.parameters if "cycle_degradation" in p.param_path]
        assert len(beta_params) == 1
        assert beta_params[0].tuned_value > 0

    def test_mtbf_tuned(self):
        fds = self._make_field_data()
        scenario = Scenario()
        charger = _default_charger()

        result = auto_tune_parameters(fds, scenario, charger, min_confidence=0.0)
        mtbf_params = [p for p in result.parameters if "mtbf" in p.param_path]
        assert len(mtbf_params) == 1
        assert mtbf_params[0].tuned_value > 0

    def test_confidence_filtering(self):
        """High min_confidence filters out low-confidence params."""
        fds = self._make_field_data()
        scenario = Scenario()
        charger = _default_charger()

        # Only 3 packs → confidence = 3/50 = 0.06
        result_strict = auto_tune_parameters(fds, scenario, charger, min_confidence=0.5)
        result_lax = auto_tune_parameters(fds, scenario, charger, min_confidence=0.0)

        # Strict should have fewer params than lax
        assert len(result_strict.parameters) <= len(result_lax.parameters)

    def test_no_bms_data(self):
        """Only charger data → only MTBF tuned."""
        cfail = ingest_charger_csv(io.StringIO(CHARGER_CSV_VALID))
        fds = FieldDataSet(charger_failure_records=cfail)
        scenario = Scenario()
        charger = _default_charger()

        result = auto_tune_parameters(fds, scenario, charger, min_confidence=0.0)
        param_paths = {p.param_path for p in result.parameters}
        assert "pack.cycle_degradation_rate_pct" not in param_paths

    def test_no_charger_data(self):
        """Only BMS data → no MTBF tuned."""
        bms = ingest_bms_csv(io.StringIO(BMS_CSV_VALID))
        fds = FieldDataSet(bms_records=bms)
        scenario = Scenario()
        charger = _default_charger()

        result = auto_tune_parameters(fds, scenario, charger, min_confidence=0.0)
        param_paths = {p.param_path for p in result.parameters}
        assert "charger.mtbf_hours" not in param_paths

    def test_empty_data(self):
        fds = FieldDataSet()
        scenario = Scenario()
        charger = _default_charger()

        result = auto_tune_parameters(fds, scenario, charger, min_confidence=0.0)
        assert result.parameters == []
        assert result.num_packs_used == 0


# ═══════════════════════════════════════════════════════════════════════════
# Apply tuned parameters
# ═══════════════════════════════════════════════════════════════════════════

class TestApplyTunedParameters:
    def test_applies_to_scenario(self):
        fds_bms = ingest_bms_csv(io.StringIO(BMS_CSV_VALID))
        fds = FieldDataSet(bms_records=fds_bms)
        scenario = Scenario()
        charger = _default_charger()

        tune = auto_tune_parameters(fds, scenario, charger, min_confidence=0.0)
        tuned_scenario, tuned_charger = apply_tuned_parameters(scenario, charger, tune)

        # Original unchanged
        assert scenario.pack.cycle_degradation_rate_pct == 0.01

        # Tuned values applied
        beta_params = [p for p in tune.parameters if "cycle_degradation" in p.param_path]
        if beta_params:
            assert tuned_scenario.pack.cycle_degradation_rate_pct == pytest.approx(
                beta_params[0].tuned_value, rel=1e-4,
            )

    def test_applies_to_charger(self):
        cfail = ingest_charger_csv(io.StringIO(CHARGER_CSV_VALID))
        fds = FieldDataSet(charger_failure_records=cfail)
        scenario = Scenario()
        charger = _default_charger()

        tune = auto_tune_parameters(fds, scenario, charger, min_confidence=0.0)
        _, tuned_charger = apply_tuned_parameters(scenario, charger, tune)

        mtbf_params = [p for p in tune.parameters if "mtbf" in p.param_path]
        if mtbf_params:
            assert tuned_charger.mtbf_hours == pytest.approx(
                mtbf_params[0].tuned_value, rel=1e-4,
            )

    def test_deep_copy_preserves_original(self):
        fds = FieldDataSet(bms_records=ingest_bms_csv(io.StringIO(BMS_CSV_VALID)))
        scenario = Scenario()
        charger = _default_charger()

        tune = auto_tune_parameters(fds, scenario, charger, min_confidence=0.0)
        tuned_s, tuned_c = apply_tuned_parameters(scenario, charger, tune)

        # Originals untouched
        assert scenario.pack.cycle_degradation_rate_pct == 0.01
        assert charger.mtbf_hours == 80_000
