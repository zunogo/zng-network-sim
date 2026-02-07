"""Tests for engine/pack_tco.py — fleet-level battery pack failure TCO.

MTBF is a population statistic.  All failure, repair, and replacement
metrics are computed across the entire pack fleet.

  fleet_operating_hours = hrs/day × 365 × years × total_packs
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
from zng_simulator.engine.pack_tco import compute_pack_tco


# ── Helpers ─────────────────────────────────────────────────────────────

def _make_pack_tco(
    station: StationConfig | None = None,
    pack: PackSpec | None = None,
    vehicle: VehicleConfig | None = None,
    charger: ChargerVariant | None = None,
    chaos: ChaosConfig | None = None,
    revenue: RevenueConfig | None = None,
    sim: SimulationConfig | None = None,
    initial_packs: int | None = None,
):
    """Convenience: compute derived + pack TCO with sensible defaults."""
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
        mtbf_hours=50_000, mttr_hours=4.0, repair_cost_per_event=2_000,
        replacement_threshold=3, full_replacement_cost=15_000,
        spare_packs_cost_per_station=30_000,
    )
    s = station or StationConfig(
        cabinet_cost=50_000, site_prep_cost=30_000, grid_connection_cost=25_000,
        software_cost=100_000, security_deposit=20_000,
        num_stations=5, docks_per_station=8, operating_hours_per_day=18,
    )
    c = charger or ChargerVariant(
        name="Budget-1kW", purchase_cost_per_slot=8_000, rated_power_w=1_000,
        charging_efficiency_pct=0.90, mtbf_hours=8_000, mttr_hours=24,
    )
    ch = chaos or ChaosConfig(
        sabotage_pct_per_month=0.005, aggressiveness_index=1.0,
        thermal_throttling_factor=1.0,
    )
    r = revenue or RevenueConfig(
        price_per_swap=40.0, initial_fleet_size=200, monthly_fleet_additions=50,
    )
    sm = sim or SimulationConfig(horizon_months=60)

    derived = compute_derived_params(v, p, c, s, ch)

    if initial_packs is None:
        total_docks = s.num_stations * s.docks_per_station
        initial_packs = (
            v.packs_per_vehicle * r.initial_fleet_size
            + total_docks
            + int(math.ceil(v.packs_per_vehicle * r.initial_fleet_size * 0.10))
        )

    ptco = compute_pack_tco(p, derived, v, r, sm, s, initial_packs)
    return derived, ptco


# ── Tests ───────────────────────────────────────────────────────────────

def test_fleet_failures_basic():
    """Fleet failures = fleet_hours / MTBF.
    With defaults: initial_packs = 2×200 + 40 + ceil(2×200×0.10) = 480.
    18 hrs/day × 365 × 5 yr × 480 = 15,768,000 fleet hours.
    15,768,000 / 50,000 = 315.36 failures.
    """
    _, ptco = _make_pack_tco()

    initial_packs = 2 * 200 + 40 + int(math.ceil(2 * 200 * 0.10))  # 480
    fleet_hours = 18 * 365 * 5 * initial_packs
    expected_failures = fleet_hours / 50_000

    assert ptco.total_packs == initial_packs
    assert abs(ptco.fleet_operating_hours - fleet_hours) < 1.0
    assert abs(ptco.expected_failures - round(expected_failures, 2)) < 0.5


def test_availability():
    """Availability = MTBF / (MTBF + MTTR) = 50000 / 50004."""
    _, ptco = _make_pack_tco()
    expected = 50_000 / (50_000 + 4)
    assert abs(ptco.availability - expected) < 0.0001


def test_replacements_fleet_level():
    """Replacements = floor(fleet_failures / threshold)."""
    _, ptco = _make_pack_tco()

    initial_packs = 2 * 200 + 40 + int(math.ceil(2 * 200 * 0.10))
    fleet_hours = 18 * 365 * 5 * initial_packs
    expected_failures = fleet_hours / 50_000
    expected_replacements = int(math.floor(expected_failures / 3))

    assert ptco.num_replacements == expected_replacements
    assert ptco.num_replacements > 0  # fleet-level should find replacements


def test_downtime_equals_failures_times_mttr():
    _, ptco = _make_pack_tco()
    expected = ptco.expected_failures * 4.0  # MTTR = 4
    assert abs(ptco.total_downtime_hours - round(expected, 2)) < 0.5


def test_failure_tco_excludes_purchase():
    """Failure TCO covers repair + replacement + lost_revenue + spares.
    Purchase cost is NOT included (that's in degradation)."""
    _, ptco = _make_pack_tco()

    expected_total = (
        ptco.total_repair_cost
        + ptco.total_replacement_cost
        + ptco.lost_revenue_from_downtime
        + ptco.spare_inventory_cost
    )
    assert abs(ptco.total_failure_tco - round(expected_total, 2)) < 1.0


def test_spare_inventory_per_station():
    """Spare cost = spare_packs_cost_per_station × num_stations."""
    _, ptco = _make_pack_tco()
    expected = 30_000 * 5  # 150,000
    assert abs(ptco.spare_inventory_cost - expected) < 1.0


def test_failure_cost_per_cycle_positive():
    """With realistic MTBF, failure cost per cycle should be > 0."""
    _, ptco = _make_pack_tco()
    assert ptco.failure_cost_per_cycle > 0


def test_high_mtbf_low_failure_cost():
    """Higher MTBF → fewer failures → lower failure cost per cycle."""
    p_low = PackSpec(
        mtbf_hours=50_000, mttr_hours=4, repair_cost_per_event=2_000,
        replacement_threshold=3, full_replacement_cost=15_000,
        spare_packs_cost_per_station=30_000,
    )
    p_high = PackSpec(
        mtbf_hours=200_000, mttr_hours=4, repair_cost_per_event=2_000,
        replacement_threshold=3, full_replacement_cost=15_000,
        spare_packs_cost_per_station=30_000,
    )
    _, ptco_low = _make_pack_tco(pack=p_low)
    _, ptco_high = _make_pack_tco(pack=p_high)

    assert ptco_high.expected_failures < ptco_low.expected_failures
    assert ptco_high.failure_cost_per_cycle < ptco_low.failure_cost_per_cycle


def test_cpc_battery_includes_failure_cost(
    vehicle: VehicleConfig, pack: PackSpec, budget_charger: ChargerVariant,
    station: StationConfig, opex, chaos: ChaosConfig,
    revenue: RevenueConfig, sim_config: SimulationConfig,
):
    """CPC battery = degradation + failure_cost_per_cycle."""
    from zng_simulator.engine.charger_tco import compute_charger_tco
    from zng_simulator.engine.cost_per_cycle import compute_cpc_waterfall

    derived = compute_derived_params(vehicle, pack, budget_charger, station, chaos)
    charger_tco = compute_charger_tco(budget_charger, derived, vehicle, revenue, sim_config, station)

    total_docks = station.num_stations * station.docks_per_station
    initial_packs = (
        vehicle.packs_per_vehicle * revenue.initial_fleet_size
        + total_docks
        + int(math.ceil(vehicle.packs_per_vehicle * revenue.initial_fleet_size * 0.10))
    )
    ptco = compute_pack_tco(pack, derived, vehicle, revenue, sim_config, station, initial_packs)
    cpc = compute_cpc_waterfall(derived, pack, budget_charger, opex, chaos, station, vehicle, charger_tco, ptco)

    # Degradation component
    degradation = (pack.unit_cost - pack.second_life_salvage_value) / derived.pack_lifetime_cycles

    # Battery should be degradation + failure
    assert abs(cpc.battery - round(degradation + ptco.failure_cost_per_cycle, 4)) < 0.01
    assert cpc.battery > degradation  # failure cost adds something
