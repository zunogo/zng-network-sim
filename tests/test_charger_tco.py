"""Tests for engine/charger_tco.py — fleet-level MTBF-based TCO.

MTBF is a population/statistical measure.  All failure, repair, and
replacement metrics are computed at the fleet level:

  fleet_operating_hours = hrs/day × 365 × years × total_docks
  expected_failures     = fleet_operating_hours / MTBF
  replacements          = floor(failures / threshold)
"""

from __future__ import annotations

import math

from zng_simulator.config import (
    ChargerVariant, VehicleConfig, RevenueConfig, SimulationConfig,
    StationConfig, PackSpec, ChaosConfig,
)
from zng_simulator.engine.derived import compute_derived_params
from zng_simulator.engine.charger_tco import compute_charger_tco


# ── Helpers ─────────────────────────────────────────────────────────────

def _make_tco(
    station: StationConfig,
    charger: ChargerVariant,
    vehicle: VehicleConfig | None = None,
    pack: PackSpec | None = None,
    chaos: ChaosConfig | None = None,
    revenue: RevenueConfig | None = None,
    sim: SimulationConfig | None = None,
):
    """Convenience: compute derived + TCO with sensible defaults."""
    v = vehicle or VehicleConfig(
        name="Heavy 2W", packs_per_vehicle=2, pack_capacity_kwh=1.28,
        avg_daily_km=100, energy_consumption_wh_per_km=30,
        swap_time_minutes=2.0, range_anxiety_buffer_pct=0.20,
    )
    p = pack or PackSpec(
        name="1.28 kWh NMC", nominal_capacity_kwh=1.28, chemistry="NMC",
        unit_cost=15_000, cycle_life_to_retirement=1_200,
        cycle_degradation_rate_pct=0.05, depth_of_discharge_pct=0.80,
        retirement_soh_pct=0.70, second_life_salvage_value=3_000,
        weight_kg=6.5, aggressiveness_multiplier=1.0,
    )
    ch = chaos or ChaosConfig(
        sabotage_pct_per_month=0.005, aggressiveness_index=1.0,
        thermal_throttling_factor=1.0,
    )
    r = revenue or RevenueConfig(
        price_per_swap=40.0, initial_fleet_size=200, monthly_fleet_additions=50,
    )
    s = sim or SimulationConfig(horizon_months=60)
    derived = compute_derived_params(v, p, charger, station, ch)
    tco = compute_charger_tco(charger, derived, v, r, s, station)
    return derived, tco


# ── Tests ───────────────────────────────────────────────────────────────

def test_fleet_failures_simple_division(
    vehicle: VehicleConfig, pack: PackSpec, budget_charger: ChargerVariant,
    station: StationConfig, revenue: RevenueConfig, sim_config: SimulationConfig,
    chaos: ChaosConfig,
):
    """Fleet failures = fleet_operating_hours / MTBF.
    Station: 5 stations × 8 docks = 40 docks.
    18 hrs/day × 365 × 5 yr × 40 docks = 1,314,000 fleet hours.
    1,314,000 / 8,000 = 164.25 failures.
    """
    derived = compute_derived_params(vehicle, pack, budget_charger, station, chaos)
    tco = compute_charger_tco(budget_charger, derived, vehicle, revenue, sim_config, station)

    total_docks = 5 * 8  # 40
    fleet_hours = 18 * 365 * 5 * total_docks  # 1,314,000
    expected = fleet_hours / 8_000  # 164.25
    assert tco.total_docks == total_docks
    assert abs(tco.fleet_operating_hours - fleet_hours) < 1.0
    assert abs(tco.expected_failures_over_horizon - round(expected, 2)) < 0.5


def test_availability_is_derived_output(
    vehicle: VehicleConfig, pack: PackSpec, budget_charger: ChargerVariant,
    station: StationConfig, revenue: RevenueConfig, sim_config: SimulationConfig,
    chaos: ChaosConfig,
):
    """Availability = MTBF / (MTBF + MTTR) — a steady-state statistic."""
    derived = compute_derived_params(vehicle, pack, budget_charger, station, chaos)
    tco = compute_charger_tco(budget_charger, derived, vehicle, revenue, sim_config, station)

    expected_avail = 8_000 / (8_000 + 24)
    assert abs(tco.availability - expected_avail) < 0.0001


def test_replacements_fleet_level(
    vehicle: VehicleConfig, pack: PackSpec, budget_charger: ChargerVariant,
    station: StationConfig, revenue: RevenueConfig, sim_config: SimulationConfig,
    chaos: ChaosConfig,
):
    """Replacements = floor(fleet_failures / threshold).
    fleet_failures ≈ 164.25 → floor(164.25 / 3) = 54 replacements.
    """
    derived = compute_derived_params(vehicle, pack, budget_charger, station, chaos)
    tco = compute_charger_tco(budget_charger, derived, vehicle, revenue, sim_config, station)

    fleet_hours = 18 * 365 * 5 * 40
    expected_failures = fleet_hours / 8_000
    expected_replacements = int(math.floor(expected_failures / 3))
    assert tco.num_replacements == expected_replacements


def test_per_dock_would_miss_replacements():
    """Demonstrate the core insight: with high MTBF, per-dock gives 0
    replacements but fleet-level gives many.

    250 docks, 21 hrs/day, MTBF 80,000, 5 years, threshold 3.
    Per dock: 38,325 hrs → 0.479 failures → floor(0.479/3) = 0 replacements.
    Fleet:    9,581,250 hrs → 119.77 failures → floor(119.77/3) = 39 replacements.
    """
    s = StationConfig(
        num_stations=5, docks_per_station=50, operating_hours_per_day=21.0,
        cabinet_cost=50_000, site_prep_cost=30_000, grid_connection_cost=500_000,
        software_cost=100_000, security_deposit=20_000,
    )
    c = ChargerVariant(
        name="HighMTBF", mtbf_hours=80_000, mttr_hours=24,
        purchase_cost_per_slot=15_000, replacement_threshold=3,
        full_replacement_cost=9_500,
    )
    _, tco = _make_tco(s, c)

    total_docks = 250
    per_dock_hours = 21 * 365 * 5  # 38,325
    per_dock_failures = per_dock_hours / 80_000  # 0.47906
    per_dock_replacements = int(math.floor(per_dock_failures / 3))  # 0

    fleet_hours = per_dock_hours * total_docks  # 9,581,250
    fleet_failures = fleet_hours / 80_000  # 119.766
    fleet_replacements = int(math.floor(fleet_failures / 3))  # 39

    # Per-dock approach would give 0 × 250 = 0 replacements (WRONG)
    assert per_dock_replacements == 0
    # Fleet approach gives 39 replacements (CORRECT)
    assert fleet_replacements == 39

    # Our implementation uses fleet-level
    assert tco.total_docks == total_docks
    assert abs(tco.expected_failures_over_horizon - round(fleet_failures, 2)) < 0.5
    assert tco.num_replacements == fleet_replacements


def test_downtime_equals_failures_times_mttr(
    vehicle: VehicleConfig, pack: PackSpec, budget_charger: ChargerVariant,
    station: StationConfig, revenue: RevenueConfig, sim_config: SimulationConfig,
    chaos: ChaosConfig,
):
    derived = compute_derived_params(vehicle, pack, budget_charger, station, chaos)
    tco = compute_charger_tco(budget_charger, derived, vehicle, revenue, sim_config, station)

    expected_downtime = tco.expected_failures_over_horizon * budget_charger.mttr_hours
    assert abs(tco.total_downtime_hours - round(expected_downtime, 2)) < 0.5


def test_premium_fewer_failures_higher_availability(
    vehicle: VehicleConfig, pack: PackSpec,
    budget_charger: ChargerVariant, premium_charger: ChargerVariant,
    station: StationConfig, revenue: RevenueConfig, sim_config: SimulationConfig,
    chaos: ChaosConfig,
):
    d_b = compute_derived_params(vehicle, pack, budget_charger, station, chaos)
    d_p = compute_derived_params(vehicle, pack, premium_charger, station, chaos)
    tco_b = compute_charger_tco(budget_charger, d_b, vehicle, revenue, sim_config, station)
    tco_p = compute_charger_tco(premium_charger, d_p, vehicle, revenue, sim_config, station)

    assert tco_p.expected_failures_over_horizon < tco_b.expected_failures_over_horizon
    assert tco_p.availability > tco_b.availability


def test_tco_includes_all_components(
    vehicle: VehicleConfig, pack: PackSpec, budget_charger: ChargerVariant,
    station: StationConfig, revenue: RevenueConfig, sim_config: SimulationConfig,
    chaos: ChaosConfig,
):
    derived = compute_derived_params(vehicle, pack, budget_charger, station, chaos)
    tco = compute_charger_tco(budget_charger, derived, vehicle, revenue, sim_config, station)

    expected_total = (
        tco.purchase_cost
        + tco.total_repair_cost
        + tco.total_replacement_cost
        + tco.lost_revenue_from_downtime
        + tco.spare_inventory_cost
    )
    assert abs(tco.total_tco - round(expected_total, 2)) < 1.0


def test_cycles_served_less_than_theoretical_max(
    vehicle: VehicleConfig, pack: PackSpec, budget_charger: ChargerVariant,
    station: StationConfig, revenue: RevenueConfig, sim_config: SimulationConfig,
    chaos: ChaosConfig,
):
    """Downtime reduces fleet cycles served below theoretical maximum."""
    derived = compute_derived_params(vehicle, pack, budget_charger, station, chaos)
    tco = compute_charger_tco(budget_charger, derived, vehicle, revenue, sim_config, station)

    total_docks = station.num_stations * station.docks_per_station
    theoretical_max = derived.cycles_per_day_per_dock * 365 * 5 * total_docks
    assert tco.cycles_served_over_horizon < theoretical_max


def test_fleet_level_500_chargers():
    """500 chargers, 20 hrs/day, MTBF 80,000, 5 years.
    Fleet hours = 20 × 365 × 5 × 500 = 18,250,000.
    Failures = 18,250,000 / 80,000 = 228.125.
    """
    s = StationConfig(
        num_stations=50, docks_per_station=10, operating_hours_per_day=20.0,
        cabinet_cost=50_000, site_prep_cost=30_000, grid_connection_cost=25_000,
        software_cost=100_000, security_deposit=20_000,
    )
    c = ChargerVariant(
        name="test", mtbf_hours=80_000, mttr_hours=48,
    )
    _, tco = _make_tco(s, c)

    fleet_hours = 20 * 365 * 5 * 500  # 18,250,000
    fleet_failures = fleet_hours / 80_000  # 228.125

    assert tco.total_docks == 500
    assert abs(tco.fleet_operating_hours - fleet_hours) < 1.0
    assert abs(tco.expected_failures_over_horizon - round(fleet_failures, 2)) < 0.5


def test_purchase_cost_is_fleet_level(
    vehicle: VehicleConfig, pack: PackSpec, budget_charger: ChargerVariant,
    station: StationConfig, revenue: RevenueConfig, sim_config: SimulationConfig,
    chaos: ChaosConfig,
):
    """Purchase cost in TCO = total_docks × cost_per_slot."""
    derived = compute_derived_params(vehicle, pack, budget_charger, station, chaos)
    tco = compute_charger_tco(budget_charger, derived, vehicle, revenue, sim_config, station)

    total_docks = station.num_stations * station.docks_per_station
    expected = budget_charger.purchase_cost_per_slot * total_docks
    assert abs(tco.purchase_cost - expected) < 1.0


def test_spare_inventory_is_per_station(
    vehicle: VehicleConfig, pack: PackSpec, budget_charger: ChargerVariant,
    station: StationConfig, revenue: RevenueConfig, sim_config: SimulationConfig,
    chaos: ChaosConfig,
):
    """Spare inventory = spare_cost × num_stations."""
    derived = compute_derived_params(vehicle, pack, budget_charger, station, chaos)
    tco = compute_charger_tco(budget_charger, derived, vehicle, revenue, sim_config, station)

    expected = budget_charger.spare_inventory_cost * station.num_stations
    assert abs(tco.spare_inventory_cost - expected) < 1.0
