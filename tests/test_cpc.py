"""Tests for engine/cost_per_cycle.py."""

from __future__ import annotations

import math

from zng_simulator.config import (
    VehicleConfig, PackSpec, ChargerVariant, StationConfig,
    OpExConfig, ChaosConfig, RevenueConfig, SimulationConfig,
)
from zng_simulator.engine.derived import compute_derived_params
from zng_simulator.engine.charger_tco import compute_charger_tco
from zng_simulator.engine.pack_tco import compute_pack_tco
from zng_simulator.engine.cost_per_cycle import compute_cpc_waterfall


def _make_cpc(vehicle, pack, budget_charger, station, opex, chaos, revenue, sim_config):
    """Helper: compute full CPC pipeline."""
    derived = compute_derived_params(vehicle, pack, budget_charger, station, chaos)
    tco = compute_charger_tco(budget_charger, derived, vehicle, revenue, sim_config, station)
    total_docks = station.num_stations * station.docks_per_station
    initial_packs = (
        vehicle.packs_per_vehicle * revenue.initial_fleet_size
        + total_docks
        + int(math.ceil(vehicle.packs_per_vehicle * revenue.initial_fleet_size * 0.10))
    )
    ptco = compute_pack_tco(pack, derived, vehicle, revenue, sim_config, station, initial_packs)
    cpc = compute_cpc_waterfall(derived, pack, budget_charger, opex, chaos, station, vehicle, tco, ptco)
    return derived, tco, ptco, cpc


def test_battery_component(
    vehicle: VehicleConfig, pack: PackSpec, budget_charger: ChargerVariant,
    station: StationConfig, opex: OpExConfig, chaos: ChaosConfig,
    revenue: RevenueConfig, sim_config: SimulationConfig,
):
    derived, _, ptco, cpc = _make_cpc(vehicle, pack, budget_charger, station, opex, chaos, revenue, sim_config)

    # Degradation: (15000 - 3000) / 600 = 20.0
    degradation = (15_000 - 3_000) / 600
    # Battery = degradation + failure_cost_per_cycle
    expected = degradation + ptco.failure_cost_per_cycle
    assert abs(cpc.battery - round(expected, 4)) < 0.01


def test_electricity_component(
    vehicle: VehicleConfig, pack: PackSpec, budget_charger: ChargerVariant,
    station: StationConfig, opex: OpExConfig, chaos: ChaosConfig,
    revenue: RevenueConfig, sim_config: SimulationConfig,
):
    _, _, _, cpc = _make_cpc(vehicle, pack, budget_charger, station, opex, chaos, revenue, sim_config)

    # (1.28 / 0.90) × 8.0 = 11.3778
    expected = (1.28 / 0.90) * 8.0
    assert abs(cpc.electricity - round(expected, 4)) < 0.01


def test_total_is_sum_of_components(
    vehicle: VehicleConfig, pack: PackSpec, budget_charger: ChargerVariant,
    station: StationConfig, opex: OpExConfig, chaos: ChaosConfig,
    revenue: RevenueConfig, sim_config: SimulationConfig,
):
    _, _, _, cpc = _make_cpc(vehicle, pack, budget_charger, station, opex, chaos, revenue, sim_config)

    component_sum = (
        cpc.battery + cpc.charger + cpc.electricity + cpc.real_estate
        + cpc.maintenance + cpc.insurance + cpc.sabotage + cpc.logistics + cpc.overhead
    )
    assert abs(cpc.total - component_sum) < 0.01


def test_all_components_non_negative(
    vehicle: VehicleConfig, pack: PackSpec, budget_charger: ChargerVariant,
    station: StationConfig, opex: OpExConfig, chaos: ChaosConfig,
    revenue: RevenueConfig, sim_config: SimulationConfig,
):
    _, _, _, cpc = _make_cpc(vehicle, pack, budget_charger, station, opex, chaos, revenue, sim_config)

    for field in ["battery", "charger", "electricity", "real_estate", "maintenance",
                  "insurance", "sabotage", "logistics", "overhead", "total"]:
        assert getattr(cpc, field) >= 0, f"{field} should be non-negative"
