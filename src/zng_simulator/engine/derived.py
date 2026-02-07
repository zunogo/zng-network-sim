"""Derived operational parameters — §6.1.

Pure arithmetic: vehicle + pack + charger + station inputs → DerivedParams.
"""

from __future__ import annotations

import math

from zng_simulator.config.vehicle import VehicleConfig
from zng_simulator.config.battery import PackSpec
from zng_simulator.config.charger import ChargerVariant
from zng_simulator.config.station import StationConfig
from zng_simulator.config.chaos import ChaosConfig
from zng_simulator.config.revenue import RevenueConfig
from zng_simulator.models.results import DerivedParams


def compute_derived_params(
    vehicle: VehicleConfig,
    pack: PackSpec,
    charger: ChargerVariant,
    station: StationConfig,
    chaos: ChaosConfig | None = None,
    revenue: RevenueConfig | None = None,
) -> DerivedParams:
    """Compute all derived operational parameters from raw inputs."""

    # ── Energy per swap cycle ──────────────────────────────────────────
    # Driver swaps at range_anxiety_buffer SoC (e.g. 20%), not 0%.
    # This is a behavioural assumption — not a hard limit from us.
    # Energy consumed per pack between visits:
    energy_per_swap_cycle_per_pack_kwh = vehicle.pack_capacity_kwh * (1.0 - vehicle.range_anxiety_buffer_pct)

    # Total energy refilled per swap VISIT (vehicle gets all packs swapped):
    energy_per_swap_cycle_per_vehicle_kwh = (
        vehicle.packs_per_vehicle * energy_per_swap_cycle_per_pack_kwh
    )

    # Nameplate total
    total_energy_per_vehicle_kwh = vehicle.packs_per_vehicle * vehicle.pack_capacity_kwh

    # ── Daily energy need ──────────────────────────────────────────────
    daily_energy_need_wh = vehicle.avg_daily_km * vehicle.energy_consumption_wh_per_km

    # ── Swap visits per vehicle per day ────────────────────────────────
    # A "swap visit" = one trip to the station where ALL packs are swapped.
    # visits/day = daily_energy / total_energy_refilled_per_visit
    energy_per_visit_wh = energy_per_swap_cycle_per_vehicle_kwh * 1_000
    swap_visits_per_vehicle_per_day = (
        daily_energy_need_wh / energy_per_visit_wh if energy_per_visit_wh > 0 else 0.0
    )

    # ── Charge time per pack (minutes) ─────────────────────────────────
    rated_power_kw = charger.rated_power_w / 1_000
    charge_time_minutes = (
        (vehicle.pack_capacity_kwh / (rated_power_kw * charger.charging_efficiency_pct)) * 60
        if rated_power_kw > 0 and charger.charging_efficiency_pct > 0
        else float("inf")
    )

    # ── Effective C-rate ───────────────────────────────────────────────
    effective_c_rate = rated_power_kw / vehicle.pack_capacity_kwh if vehicle.pack_capacity_kwh > 0 else 0.0

    # ── Cycles per day per dock (throughput ceiling) ───────────────────
    cycles_per_day_per_dock = (
        (station.operating_hours_per_day * 60) / charge_time_minutes
        if charge_time_minutes > 0
        else 0.0
    )

    # ── Pack lifetime cycles ───────────────────────────────────────────
    beta_fraction = pack.cycle_degradation_rate_pct / 100.0
    aggressiveness = chaos.aggressiveness_index if chaos else 1.0
    effective_beta = beta_fraction * aggressiveness
    soh_budget = 1.0 - pack.retirement_soh_pct
    pack_lifetime_cycles = int(math.floor(soh_budget / effective_beta)) if effective_beta > 0 else 999_999

    # ── Network totals ─────────────────────────────────────────────────
    total_docks = station.num_stations * station.docks_per_station
    cycles_per_month_per_station = cycles_per_day_per_dock * station.docks_per_station * 30
    total_network_cycles_per_month = cycles_per_month_per_station * station.num_stations

    # ── Fleet inventory ──────────────────────────────────────────────
    # Packs on vehicles: riding with the fleet.
    # Packs in docks: sitting at stations being charged — this IS the float.
    # Total = on vehicles + in docks (no separate float on top).
    initial_fleet_size = revenue.initial_fleet_size if revenue else 0
    packs_on_vehicles = vehicle.packs_per_vehicle * initial_fleet_size
    packs_in_docks = total_docks  # the float / buffer inventory
    total_packs = packs_on_vehicles + packs_in_docks

    return DerivedParams(
        energy_per_swap_cycle_per_pack_kwh=round(energy_per_swap_cycle_per_pack_kwh, 4),
        energy_per_swap_cycle_per_vehicle_kwh=round(energy_per_swap_cycle_per_vehicle_kwh, 4),
        total_energy_per_vehicle_kwh=round(total_energy_per_vehicle_kwh, 4),
        daily_energy_need_wh=round(daily_energy_need_wh, 2),
        swap_visits_per_vehicle_per_day=round(swap_visits_per_vehicle_per_day, 4),
        charge_time_minutes=round(charge_time_minutes, 2),
        effective_c_rate=round(effective_c_rate, 4),
        cycles_per_day_per_dock=round(cycles_per_day_per_dock, 2),
        pack_lifetime_cycles=pack_lifetime_cycles,
        total_docks=total_docks,
        cycles_per_month_per_station=round(cycles_per_month_per_station, 2),
        total_network_cycles_per_month=round(total_network_cycles_per_month, 2),
        initial_fleet_size=initial_fleet_size,
        packs_on_vehicles=packs_on_vehicles,
        packs_in_docks=packs_in_docks,
        total_packs=total_packs,
    )
