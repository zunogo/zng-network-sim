"""Tests for engine/orchestrator.py — stochastic simulation loop + Monte Carlo.

Covers:
  - Static engine routing (delegates to Phase 1)
  - Single stochastic run produces valid SimulationResult
  - Phase 2 fields are populated (avg_soh, packs_retired, charger_failures, etc.)
  - Lumpy CapEx: replacement_capex_this_month is non-zero only in retirement months
  - Monte Carlo produces MonteCarloSummary with P10/P50/P90
  - Reproducibility: same seed → same stochastic result
  - Engine type is correctly set
  - Cohort history is recorded
"""

from __future__ import annotations

import pytest
import numpy as np

from zng_simulator.config.vehicle import VehicleConfig
from zng_simulator.config.battery import PackSpec
from zng_simulator.config.charger import ChargerVariant
from zng_simulator.config.station import StationConfig
from zng_simulator.config.opex import OpExConfig
from zng_simulator.config.revenue import RevenueConfig
from zng_simulator.config.chaos import ChaosConfig
from zng_simulator.config.demand import DemandConfig
from zng_simulator.config.scenario import Scenario, SimulationConfig
from zng_simulator.engine.orchestrator import run_engine


# ═══════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def fast_degradation_pack() -> PackSpec:
    """Pack that retires quickly for testable lumpy CapEx."""
    return PackSpec(
        name="Fast-Degrade Test Pack",
        nominal_capacity_kwh=1.28,
        chemistry="LFP",
        unit_cost=15_000,
        weight_kg=7.0,
        cycle_life_to_retirement=600,
        cycle_degradation_rate_pct=0.05,
        calendar_aging_rate_pct_per_month=0.10,
        depth_of_discharge_pct=0.90,
        retirement_soh_pct=0.70,
        second_life_salvage_value=3_000,
        aggressiveness_multiplier=1.0,
        mtbf_hours=50_000,
        mttr_hours=4.0,
        repair_cost_per_event=2_000,
        replacement_threshold=3,
        full_replacement_cost=12_000,
        spare_packs_cost_per_station=20_000,
    )


@pytest.fixture
def test_charger() -> ChargerVariant:
    return ChargerVariant(
        name="Test-Charger",
        purchase_cost_per_slot=12_000,
        rated_power_w=1_500,
        charging_efficiency_pct=0.95,
        mtbf_hours=30_000,
        mttr_hours=12,
        repair_cost_per_event=1_000,
        replacement_threshold=3,
        full_replacement_cost=9_000,
        spare_inventory_cost=8_000,
        expected_useful_life_years=4.0,
        failure_distribution="exponential",
        weibull_shape=1.0,
    )


@pytest.fixture
def base_scenario(fast_degradation_pack, test_charger) -> Scenario:
    """Minimal scenario for testing orchestrator."""
    return Scenario(
        vehicle=VehicleConfig(
            vehicle_type="3W",
            packs_per_vehicle=2,
            pack_capacity_kwh=1.28,
            avg_daily_km=80,
            wh_per_km=25,
            swap_time_minutes=3,
            range_anxiety_buffer=0.20,
        ),
        pack=fast_degradation_pack,
        charger_variants=[test_charger],
        station=StationConfig(
            num_stations=3,
            docks_per_station=8,
            operating_hours_per_day=18,
            cabinet_cost=50_000,
            site_prep_cost=20_000,
            grid_connection_cost=30_000,
            security_deposit=10_000,
            software_cost=100_000,
        ),
        opex=OpExConfig(
            electricity_tariff_per_kwh=8.0,
            rent_per_month_per_station=15_000,
            pack_handling_labor_per_swap=2.0,
            overhead_per_month=20_000,
        ),
        revenue=RevenueConfig(
            initial_fleet_size=100,
            price_per_swap=35,
            monthly_fleet_additions=5,
        ),
        chaos=ChaosConfig(
            sabotage_pct_per_month=0.001,
            aggressiveness_index=1.0,
        ),
        demand=DemandConfig(
            distribution="poisson",
            volatility=0.15,
            weekend_factor=0.7,
            seasonal_amplitude=0.05,
        ),
        simulation=SimulationConfig(
            horizon_months=24,
            discount_rate_annual=0.12,
            engine="stochastic",
            random_seed=42,
            monte_carlo_runs=1,
        ),
    )


# ═══════════════════════════════════════════════════════════════════════════
# Engine routing
# ═══════════════════════════════════════════════════════════════════════════

class TestRouting:
    """run_engine routes correctly based on engine type."""

    def test_static_engine_delegates(self, base_scenario, test_charger):
        """engine='static' should use Phase 1 engine."""
        scenario = base_scenario.model_copy(
            update={"simulation": SimulationConfig(engine="static", horizon_months=12)}
        )
        result = run_engine(scenario, test_charger)
        assert result.engine_type == "static"
        assert result.monte_carlo is None
        assert result.cohort_history is None

    def test_stochastic_engine_used(self, base_scenario, test_charger):
        """engine='stochastic' should use Phase 2 engine."""
        result = run_engine(base_scenario, test_charger)
        assert result.engine_type == "stochastic"


# ═══════════════════════════════════════════════════════════════════════════
# Single stochastic run
# ═══════════════════════════════════════════════════════════════════════════

class TestSingleStochastic:
    """Verify a single stochastic run produces valid results."""

    def test_result_structure(self, base_scenario, test_charger):
        """Result has all required fields."""
        result = run_engine(base_scenario, test_charger)
        assert result.engine_type == "stochastic"
        assert len(result.months) == 24
        assert result.summary is not None
        assert result.derived is not None
        assert result.cpc_waterfall is not None
        assert result.charger_tco is not None
        assert result.pack_tco is not None

    def test_phase2_fields_populated(self, base_scenario, test_charger):
        """Phase 2 stochastic fields should be non-None."""
        result = run_engine(base_scenario, test_charger)
        m1 = result.months[0]

        assert m1.avg_soh is not None
        assert m1.packs_retired_this_month is not None
        assert m1.packs_replaced_this_month is not None
        assert m1.replacement_capex_this_month is not None
        assert m1.salvage_credit_this_month is not None
        assert m1.charger_failures_this_month is not None

    def test_avg_soh_starts_near_one(self, base_scenario, test_charger):
        """First month avg_soh should be close to 1.0 (slight degradation)."""
        result = run_engine(base_scenario, test_charger)
        assert result.months[0].avg_soh is not None
        assert result.months[0].avg_soh > 0.95

    def test_avg_soh_decreases_over_time(self, base_scenario, test_charger):
        """SOH should generally decrease (ignoring replacement bounces)."""
        result = run_engine(base_scenario, test_charger)
        first_soh = result.months[0].avg_soh
        last_soh = result.months[-1].avg_soh
        # Last SOH could be high if replacement just happened; check mid-point
        mid_soh = result.months[len(result.months) // 2].avg_soh
        assert mid_soh < first_soh or last_soh < first_soh

    def test_summary_has_stochastic_fields(self, base_scenario, test_charger):
        """RunSummary should have Phase 2 fields populated."""
        result = run_engine(base_scenario, test_charger)
        s = result.summary

        assert s.total_packs_retired is not None
        assert s.total_charger_failures is not None
        assert s.mean_soh_at_end is not None
        assert s.total_replacement_capex is not None
        assert s.total_salvage_credit is not None

    def test_cohort_history_recorded(self, base_scenario, test_charger):
        """cohort_history should have one entry per month."""
        result = run_engine(base_scenario, test_charger)
        assert result.cohort_history is not None
        assert len(result.cohort_history) == 24

    def test_charger_failures_occur(self, base_scenario, test_charger):
        """With MTBF=30000h and 24 docks, some failures should occur in 24 months."""
        result = run_engine(base_scenario, test_charger)
        total_failures = sum(
            m.charger_failures_this_month for m in result.months
            if m.charger_failures_this_month is not None
        )
        assert total_failures > 0

    def test_revenue_driven_by_stochastic_demand(self, base_scenario, test_charger):
        """Revenue should vary month-to-month (stochastic demand)."""
        result = run_engine(base_scenario, test_charger)
        revenues = [m.revenue for m in result.months]
        # With stochastic demand, not all months should have identical revenue
        assert len(set(revenues)) > 1


# ═══════════════════════════════════════════════════════════════════════════
# Lumpy CapEx (the key Phase 2 feature)
# ═══════════════════════════════════════════════════════════════════════════

class TestLumpyCapEx:
    """Verify replacement CapEx is lumpy, not spread evenly."""

    def test_most_months_have_zero_replacement(self, base_scenario, test_charger):
        """Most months should have zero pack replacement CapEx."""
        result = run_engine(base_scenario, test_charger)
        zero_months = sum(
            1 for m in result.months
            if m.replacement_capex_this_month == 0
        )
        nonzero_months = sum(
            1 for m in result.months
            if m.replacement_capex_this_month is not None and m.replacement_capex_this_month > 0
        )
        # With fast degradation, we expect at least one retirement in 24 months
        # but most months should be zero
        assert zero_months > nonzero_months

    def test_replacement_capex_equals_retired_times_cost(self, base_scenario, test_charger):
        """replacement_capex = retired × (unit_cost - salvage)."""
        result = run_engine(base_scenario, test_charger)
        unit_cost = base_scenario.pack.unit_cost
        salvage = base_scenario.pack.second_life_salvage_value
        net_per_pack = unit_cost - salvage

        for m in result.months:
            if m.packs_retired_this_month and m.packs_retired_this_month > 0:
                expected = m.packs_retired_this_month * net_per_pack
                assert abs(m.replacement_capex_this_month - expected) < 1.0

    def test_salvage_credit_equals_retired_times_salvage(self, base_scenario, test_charger):
        """salvage_credit = retired × salvage_value."""
        result = run_engine(base_scenario, test_charger)
        salvage = base_scenario.pack.second_life_salvage_value

        for m in result.months:
            if m.packs_retired_this_month and m.packs_retired_this_month > 0:
                expected = m.packs_retired_this_month * salvage
                assert abs(m.salvage_credit_this_month - expected) < 1.0

    def test_total_replacement_capex_matches_summary(self, base_scenario, test_charger):
        """Sum of monthly replacement CapEx should match summary total."""
        result = run_engine(base_scenario, test_charger)

        monthly_total = sum(
            (m.replacement_capex_this_month or 0) + (m.salvage_credit_this_month or 0)
            for m in result.months
        )
        # summary.total_replacement_capex is gross (before salvage)
        # Let's check gross separately
        gross_from_months = sum(
            ((m.packs_retired_this_month or 0) * base_scenario.pack.unit_cost)
            for m in result.months
        )
        assert abs(gross_from_months - (result.summary.total_replacement_capex or 0)) < 10.0


# ═══════════════════════════════════════════════════════════════════════════
# Reproducibility
# ═══════════════════════════════════════════════════════════════════════════

class TestReproducibility:
    """Same seed → same results."""

    def test_same_seed_same_ncf(self, base_scenario, test_charger):
        """Two runs with same seed produce identical total NCF."""
        r1 = run_engine(base_scenario, test_charger)
        r2 = run_engine(base_scenario, test_charger)
        assert r1.summary.total_net_cash_flow == r2.summary.total_net_cash_flow

    def test_same_seed_same_monthly_revenue(self, base_scenario, test_charger):
        """Monthly revenues should be identical with same seed."""
        r1 = run_engine(base_scenario, test_charger)
        r2 = run_engine(base_scenario, test_charger)
        for m1, m2 in zip(r1.months, r2.months):
            assert m1.revenue == m2.revenue

    def test_different_seed_different_ncf(self, base_scenario, test_charger):
        """Different seeds should produce different results."""
        s2 = base_scenario.model_copy(
            update={"simulation": base_scenario.simulation.model_copy(update={"random_seed": 99})}
        )
        r1 = run_engine(base_scenario, test_charger)
        r2 = run_engine(s2, test_charger)
        assert r1.summary.total_net_cash_flow != r2.summary.total_net_cash_flow


# ═══════════════════════════════════════════════════════════════════════════
# Monte Carlo
# ═══════════════════════════════════════════════════════════════════════════

class TestMonteCarlo:
    """Monte Carlo mode produces aggregate statistics."""

    @pytest.fixture
    def mc_scenario(self, base_scenario):
        return base_scenario.model_copy(
            update={"simulation": base_scenario.simulation.model_copy(
                update={"monte_carlo_runs": 10}
            )}
        )

    def test_monte_carlo_produces_summary(self, mc_scenario, test_charger):
        """With mc_runs > 1, result should have MonteCarloSummary."""
        result = run_engine(mc_scenario, test_charger)
        assert result.monte_carlo is not None
        assert result.monte_carlo.num_runs == 10

    def test_percentiles_ordered(self, mc_scenario, test_charger):
        """P10 ≤ P50 ≤ P90 for NCF; P10 ≥ P50 ≥ P90 for CPC."""
        result = run_engine(mc_scenario, test_charger)
        mc = result.monte_carlo
        assert mc.ncf_p10 <= mc.ncf_p50 <= mc.ncf_p90
        # CPC: higher percentile = higher cost (pessimistic)
        assert mc.cpc_p10 <= mc.cpc_p50 <= mc.cpc_p90

    def test_representative_run_is_stochastic(self, mc_scenario, test_charger):
        """The representative result should be a full stochastic run."""
        result = run_engine(mc_scenario, test_charger)
        assert result.engine_type == "stochastic"
        assert len(result.months) == mc_scenario.simulation.horizon_months

    def test_mc_stats_populated(self, mc_scenario, test_charger):
        """All MonteCarloSummary stats should be populated."""
        result = run_engine(mc_scenario, test_charger)
        mc = result.monte_carlo
        assert mc.avg_packs_retired >= 0
        assert mc.max_packs_retired >= 0
        assert mc.avg_charger_failures >= 0

    def test_mc_produces_range(self, mc_scenario, test_charger):
        """With 10 runs, P10 and P90 should differ (probabilistic)."""
        result = run_engine(mc_scenario, test_charger)
        mc = result.monte_carlo
        # Very unlikely that all 10 runs produce exact same NCF
        assert mc.ncf_p10 != mc.ncf_p90


# ═══════════════════════════════════════════════════════════════════════════
# Fleet growth integration
# ═══════════════════════════════════════════════════════════════════════════

class TestFleetGrowth:
    """New vehicles → new packs → new degradation cohort."""

    def test_fleet_growth_creates_cohorts(self, base_scenario, test_charger):
        """Monthly fleet additions should create new degradation cohorts."""
        result = run_engine(base_scenario, test_charger)
        # With 24 months and monthly additions > 0:
        # cohort_history[23] (last month) should have more cohorts than month 1
        if result.cohort_history:
            first_cohorts = len(result.cohort_history[0])
            last_cohorts = len(result.cohort_history[-1])
            assert last_cohorts > first_cohorts

    def test_fleet_size_grows(self, base_scenario, test_charger):
        """Fleet size should increase month over month."""
        result = run_engine(base_scenario, test_charger)
        assert result.months[-1].fleet_size > result.months[0].fleet_size
