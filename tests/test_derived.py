"""Tests for engine/derived.py — hand-calculated expected values."""

from __future__ import annotations

import math

from zng_simulator.config import VehicleConfig, PackSpec, ChargerVariant, StationConfig, ChaosConfig, RevenueConfig
from zng_simulator.engine.derived import compute_derived_params


def test_energy_per_swap_cycle_per_pack(vehicle: VehicleConfig, pack: PackSpec, budget_charger: ChargerVariant, station: StationConfig, chaos: ChaosConfig):
    d = compute_derived_params(vehicle, pack, budget_charger, station, chaos)
    # 1.28 × (1 - 0.20) = 1.024
    assert d.energy_per_swap_cycle_per_pack_kwh == round(1.28 * 0.80, 4)


def test_energy_per_swap_cycle_per_vehicle(vehicle: VehicleConfig, pack: PackSpec, budget_charger: ChargerVariant, station: StationConfig, chaos: ChaosConfig):
    d = compute_derived_params(vehicle, pack, budget_charger, station, chaos)
    # 2 packs × 1.024 = 2.048
    assert d.energy_per_swap_cycle_per_vehicle_kwh == round(2 * 1.28 * 0.80, 4)


def test_total_energy_per_vehicle(vehicle: VehicleConfig, pack: PackSpec, budget_charger: ChargerVariant, station: StationConfig, chaos: ChaosConfig):
    d = compute_derived_params(vehicle, pack, budget_charger, station, chaos)
    # 2 × 1.28 = 2.56
    assert d.total_energy_per_vehicle_kwh == round(2 * 1.28, 4)


def test_daily_energy_need(vehicle: VehicleConfig, pack: PackSpec, budget_charger: ChargerVariant, station: StationConfig, chaos: ChaosConfig):
    d = compute_derived_params(vehicle, pack, budget_charger, station, chaos)
    # 100 × 30 = 3000
    assert d.daily_energy_need_wh == 3_000.0


def test_swap_visits_per_vehicle_per_day(vehicle: VehicleConfig, pack: PackSpec, budget_charger: ChargerVariant, station: StationConfig, chaos: ChaosConfig):
    """Swap visits = daily_energy / total_energy_per_visit (per VEHICLE, not per pack)."""
    d = compute_derived_params(vehicle, pack, budget_charger, station, chaos)
    # energy_per_visit = 2 packs × 1.024 kWh = 2.048 kWh = 2048 Wh
    # visits/day = 3000 / 2048 ≈ 1.4648
    expected = 3_000 / (2 * 1.024 * 1_000)
    assert abs(d.swap_visits_per_vehicle_per_day - round(expected, 4)) < 0.0001


def test_single_pack_vehicle_visits():
    """A single-pack vehicle should have more visits per day than a dual-pack."""
    v1 = VehicleConfig(packs_per_vehicle=1, pack_capacity_kwh=1.28, avg_daily_km=100,
                       energy_consumption_wh_per_km=30, range_anxiety_buffer_pct=0.20)
    v2 = VehicleConfig(packs_per_vehicle=2, pack_capacity_kwh=1.28, avg_daily_km=100,
                       energy_consumption_wh_per_km=30, range_anxiety_buffer_pct=0.20)
    p = PackSpec()
    c = ChargerVariant()
    s = StationConfig()
    ch = ChaosConfig()
    d1 = compute_derived_params(v1, p, c, s, ch)
    d2 = compute_derived_params(v2, p, c, s, ch)
    # Single-pack refills less energy per visit → more visits needed
    assert d1.swap_visits_per_vehicle_per_day > d2.swap_visits_per_vehicle_per_day
    # Exactly 2× the visits
    assert abs(d1.swap_visits_per_vehicle_per_day / d2.swap_visits_per_vehicle_per_day - 2.0) < 0.01


def test_charge_time(vehicle: VehicleConfig, pack: PackSpec, budget_charger: ChargerVariant, station: StationConfig, chaos: ChaosConfig):
    d = compute_derived_params(vehicle, pack, budget_charger, station, chaos)
    # 1.28 / (1.0 × 0.90) × 60 = 85.333...
    expected = (1.28 / (1.0 * 0.90)) * 60
    assert abs(d.charge_time_minutes - round(expected, 2)) < 0.01


def test_effective_c_rate(vehicle: VehicleConfig, pack: PackSpec, budget_charger: ChargerVariant, station: StationConfig, chaos: ChaosConfig):
    d = compute_derived_params(vehicle, pack, budget_charger, station, chaos)
    expected = 1.0 / 1.28
    assert abs(d.effective_c_rate - round(expected, 4)) < 0.0001


def test_cycles_per_day_per_dock(vehicle: VehicleConfig, pack: PackSpec, budget_charger: ChargerVariant, station: StationConfig, chaos: ChaosConfig):
    d = compute_derived_params(vehicle, pack, budget_charger, station, chaos)
    charge_time = (1.28 / (1.0 * 0.90)) * 60
    expected = (18 * 60) / charge_time
    assert abs(d.cycles_per_day_per_dock - round(expected, 2)) < 0.01


def test_pack_lifetime_cycles(vehicle: VehicleConfig, pack: PackSpec, budget_charger: ChargerVariant, station: StationConfig, chaos: ChaosConfig):
    d = compute_derived_params(vehicle, pack, budget_charger, station, chaos)
    # (1.0 - 0.70) / (0.05/100 × 1.0) = 0.30 / 0.0005 = 600
    expected = int(math.floor(0.30 / 0.0005))
    assert d.pack_lifetime_cycles == expected


def test_total_docks(vehicle: VehicleConfig, pack: PackSpec, budget_charger: ChargerVariant, station: StationConfig, chaos: ChaosConfig):
    d = compute_derived_params(vehicle, pack, budget_charger, station, chaos)
    assert d.total_docks == 5 * 8


def test_fleet_inventory_with_revenue(
    vehicle: VehicleConfig, pack: PackSpec, budget_charger: ChargerVariant,
    station: StationConfig, chaos: ChaosConfig, revenue: RevenueConfig,
):
    """Fleet inventory: vehicles=200, packs/vehicle=2, docks=40 (= float).
    Packs in docks ARE the float inventory.
    """
    d = compute_derived_params(vehicle, pack, budget_charger, station, chaos, revenue)

    # Station fixture: 5 stations × 8 docks = 40 docks
    assert d.initial_fleet_size == 200
    assert d.packs_on_vehicles == 200 * 2  # 400
    assert d.packs_in_docks == 40  # = total_docks = the float
    assert d.total_packs == 400 + 40  # no separate float on top


def test_fleet_inventory_without_revenue(
    vehicle: VehicleConfig, pack: PackSpec, budget_charger: ChargerVariant,
    station: StationConfig, chaos: ChaosConfig,
):
    """Without revenue, fleet inventory defaults to 0 vehicles."""
    d = compute_derived_params(vehicle, pack, budget_charger, station, chaos)
    assert d.initial_fleet_size == 0
    assert d.packs_on_vehicles == 0
    assert d.packs_in_docks == 40  # docks still exist
    assert d.total_packs == 40  # just the dock packs
