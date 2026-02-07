"""Battery pack failure TCO — fleet-level (§6.3b).

Covers *random / unexpected* failures (BMS faults, cell swelling,
connector damage, handling damage) — NOT cycle degradation.

MTBF is a population statistic.  All metrics are fleet-level:

  fleet_operating_hours = hrs/day × 365 × years × total_packs
  expected_failures     = fleet_operating_hours / MTBF
  replacements          = floor(expected_failures / threshold)

The resulting failure_cost_per_cycle is ADDED to the degradation cost
to form the full CPC battery component.
"""

from __future__ import annotations

import math

from zng_simulator.config.battery import PackSpec
from zng_simulator.config.revenue import RevenueConfig
from zng_simulator.config.vehicle import VehicleConfig
from zng_simulator.config.scenario import SimulationConfig
from zng_simulator.config.station import StationConfig
from zng_simulator.models.results import DerivedParams, PackTCOBreakdown


def compute_pack_tco(
    pack: PackSpec,
    derived: DerivedParams,
    vehicle: VehicleConfig,
    revenue: RevenueConfig,
    simulation: SimulationConfig,
    station: StationConfig,
    initial_packs: int,
) -> PackTCOBreakdown:
    """Compute fleet-level failure TCO for battery packs.

    Core formula (fleet-level):
      Expected failures = (hrs/day × 365 × years × total_packs) / MTBF

    ``initial_packs`` = packs on vehicles + packs in docks + 10% float,
    calculated by the caller (cashflow.py).
    """
    horizon_years = simulation.horizon_months / 12.0

    # ── Fleet operating hours ──────────────────────────────────────────
    # Packs are "in service" during station operating hours — either on
    # vehicles, in chargers, or in the swap queue.
    hours_per_year_per_pack = station.operating_hours_per_day * 365
    fleet_operating_hours = hours_per_year_per_pack * horizon_years * initial_packs

    # ── Expected failures (fleet-wide) ─────────────────────────────────
    expected_failures = (
        fleet_operating_hours / pack.mtbf_hours
        if pack.mtbf_hours > 0 else 0.0
    )

    # ── Availability (derived statistic) ───────────────────────────────
    availability = (
        pack.mtbf_hours / (pack.mtbf_hours + pack.mttr_hours)
        if (pack.mtbf_hours + pack.mttr_hours) > 0 else 1.0
    )

    # ── Repair costs (fleet-wide) ──────────────────────────────────────
    total_repair_cost = expected_failures * pack.repair_cost_per_event

    # ── Full replacements (fleet-wide) ─────────────────────────────────
    num_replacements = (
        int(math.floor(expected_failures / pack.replacement_threshold))
        if pack.replacement_threshold > 0 else 0
    )
    total_replacement_cost = num_replacements * pack.full_replacement_cost

    # ── Downtime & lost revenue (fleet-wide) ───────────────────────────
    total_downtime_hours = expected_failures * pack.mttr_hours

    # Each failed pack effectively idles one dock slot for MTTR hours.
    cycles_per_hour = (
        derived.cycles_per_day_per_dock / station.operating_hours_per_day
        if station.operating_hours_per_day > 0 else 0.0
    )
    revenue_per_cycle = (
        revenue.price_per_swap / vehicle.packs_per_vehicle
        if vehicle.packs_per_vehicle > 0 else 0.0
    )
    lost_revenue = total_downtime_hours * cycles_per_hour * revenue_per_cycle

    # ── Spare inventory (per station) ──────────────────────────────────
    fleet_spare_cost = pack.spare_packs_cost_per_station * station.num_stations

    # ── Total failure TCO (excludes purchase — that's in degradation) ──
    total_failure_tco = (
        total_repair_cost
        + total_replacement_cost
        + lost_revenue
        + fleet_spare_cost
    )

    # ── Cycles served (fleet-wide, accounting for downtime) ────────────
    fleet_uptime_hours = fleet_operating_hours - total_downtime_hours
    fleet_cycles = cycles_per_hour * fleet_uptime_hours if fleet_uptime_hours > 0 else 0.0

    failure_cost_per_cycle = (
        total_failure_tco / fleet_cycles if fleet_cycles > 0 else 0.0
    )

    return PackTCOBreakdown(
        total_packs=initial_packs,
        fleet_operating_hours=round(fleet_operating_hours, 1),
        availability=round(availability, 6),
        expected_failures=round(expected_failures, 2),
        total_repair_cost=round(total_repair_cost, 2),
        num_replacements=num_replacements,
        total_replacement_cost=round(total_replacement_cost, 2),
        total_downtime_hours=round(total_downtime_hours, 2),
        lost_revenue_from_downtime=round(lost_revenue, 2),
        spare_inventory_cost=round(fleet_spare_cost, 2),
        total_failure_tco=round(total_failure_tco, 2),
        failure_cost_per_cycle=round(failure_cost_per_cycle, 4),
    )
