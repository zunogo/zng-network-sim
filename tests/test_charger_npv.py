"""Tests for charger NPV comparison (Phase 3)."""

import pytest
from zng_simulator.finance.charger_npv import compute_charger_npv
from zng_simulator.config.charger import ChargerVariant
from zng_simulator.config.station import StationConfig
from zng_simulator.config.scenario import SimulationConfig
from zng_simulator.models.results import ChargerTCOBreakdown, DerivedParams


@pytest.fixture
def charger() -> ChargerVariant:
    return ChargerVariant(
        name="Test-1kW",
        purchase_cost_per_slot=10000,
        rated_power_w=1000,
        charging_efficiency_pct=0.90,
        mtbf_hours=10000,
        mttr_hours=24,
        repair_cost_per_event=1500,
        replacement_threshold=3,
        full_replacement_cost=8000,
        spare_inventory_cost=5000,
    )


@pytest.fixture
def tco() -> ChargerTCOBreakdown:
    return ChargerTCOBreakdown(
        total_docks=40,
        purchase_cost=400_000,
        scheduled_hours_per_year_per_dock=6570,
        fleet_operating_hours=1_314_000,
        availability=0.9976,
        expected_failures_over_horizon=131.4,
        total_repair_cost=197_100,
        num_replacements=43,
        total_replacement_cost=344_000,
        total_downtime_hours=3153.6,
        lost_revenue_from_downtime=50_000,
        spare_inventory_cost=25_000,
        total_tco=1_016_100,
        cycles_served_over_horizon=2_400_000,
        cost_per_cycle=0.4234,
    )


@pytest.fixture
def derived() -> DerivedParams:
    return DerivedParams(
        energy_per_swap_cycle_per_pack_kwh=1.024,
        energy_per_swap_cycle_per_vehicle_kwh=2.048,
        total_energy_per_vehicle_kwh=2.56,
        daily_energy_need_wh=3000,
        swap_visits_per_vehicle_per_day=1.46,
        charge_time_minutes=85.33,
        effective_c_rate=0.78,
        cycles_per_day_per_dock=12.66,
        pack_lifetime_cycles=600,
        total_docks=40,
        cycles_per_month_per_station=3040,
        total_network_cycles_per_month=15200,
        initial_fleet_size=200,
        packs_on_vehicles=400,
        packs_in_docks=40,
        total_packs=440,
    )


@pytest.fixture
def sim_cfg() -> SimulationConfig:
    return SimulationConfig(
        horizon_months=60,
        discount_rate_annual=0.12,
    )


class TestChargerNPV:
    def test_npv_tco_positive(self, charger, tco, derived, sim_cfg):
        result = compute_charger_npv(charger, tco, derived, sim_cfg, StationConfig())
        assert result.npv_tco > 0

    def test_npv_less_than_undiscounted(self, charger, tco, derived, sim_cfg):
        result = compute_charger_npv(charger, tco, derived, sim_cfg, StationConfig())
        # NPV should generally be less than undiscounted since future costs are worth less
        # But purchase is at month 0 (same), so NPV ≈ undiscounted for high portion upfront
        assert result.npv_tco <= result.undiscounted_tco * 1.01  # allow small rounding

    def test_pv_purchase_equals_purchase(self, charger, tco, derived, sim_cfg):
        """PV of purchase = purchase (month 0, no discounting)."""
        result = compute_charger_npv(charger, tco, derived, sim_cfg, StationConfig())
        assert result.pv_purchase == tco.purchase_cost

    def test_discounted_cpc_positive(self, charger, tco, derived, sim_cfg):
        result = compute_charger_npv(charger, tco, derived, sim_cfg, StationConfig())
        assert result.discounted_cpc > 0

    def test_monthly_trajectory_length(self, charger, tco, derived, sim_cfg):
        result = compute_charger_npv(charger, tco, derived, sim_cfg, StationConfig())
        assert len(result.monthly_discounted_cpc) == sim_cfg.horizon_months

    def test_monthly_trajectory_converges(self, charger, tco, derived, sim_cfg):
        """Discounted CPC should decrease (or stabilize) over time as fixed costs spread."""
        result = compute_charger_npv(charger, tco, derived, sim_cfg, StationConfig())
        # First month CPC should be higher than last
        assert result.monthly_discounted_cpc[0] > result.monthly_discounted_cpc[-1]
