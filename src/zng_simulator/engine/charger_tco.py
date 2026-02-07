"""Charger TCO — fleet-level deterministic expected-value calculation (§6.3).

MTBF is a **population / statistical** measure.  It doesn't predict when
a single charger breaks — it describes the average failure rate across a
fleet of chargers.

All metrics are therefore computed at the **fleet** level:

  fleet_operating_hours = hrs/day × 365 × years × total_docks
  expected_failures     = fleet_operating_hours / MTBF
  replacements          = floor(expected_failures / threshold)

Availability = MTBF / (MTBF + MTTR) is a derived statistic.
Downtime = failures × MTTR (fleet-wide hours of dock-downtime).
"""

from __future__ import annotations

import math

from zng_simulator.config.charger import ChargerVariant
from zng_simulator.config.revenue import RevenueConfig
from zng_simulator.config.vehicle import VehicleConfig
from zng_simulator.config.scenario import SimulationConfig
from zng_simulator.config.station import StationConfig
from zng_simulator.models.results import ChargerTCOBreakdown, DerivedParams


def compute_charger_tco(
    charger: ChargerVariant,
    derived: DerivedParams,
    vehicle: VehicleConfig,
    revenue: RevenueConfig,
    simulation: SimulationConfig,
    station: StationConfig,
) -> ChargerTCOBreakdown:
    """Compute fleet-level total cost of ownership for one charger variant.

    Core formula (fleet-level):
      Expected Failures = (hrs/day × 365 × years × total_docks) / MTBF
    """
    horizon_years = simulation.horizon_months / 12.0
    total_docks = derived.total_docks  # stations × docks_per_station

    # ── Hours ──────────────────────────────────────────────────────────
    scheduled_hours_per_year_per_dock = station.operating_hours_per_day * 365
    fleet_operating_hours = (
        scheduled_hours_per_year_per_dock * horizon_years * total_docks
    )

    # ── Expected failures (fleet-wide) ─────────────────────────────────
    expected_failures = (
        fleet_operating_hours / charger.mtbf_hours
        if charger.mtbf_hours > 0 else 0.0
    )

    # ── Availability (derived statistic) ───────────────────────────────
    availability = (
        charger.mtbf_hours / (charger.mtbf_hours + charger.mttr_hours)
        if (charger.mtbf_hours + charger.mttr_hours) > 0 else 1.0
    )

    # ── Repair costs (fleet-wide) ──────────────────────────────────────
    total_repair_cost = expected_failures * charger.repair_cost_per_event

    # ── Full replacements (fleet-wide) ─────────────────────────────────
    # After every `replacement_threshold` failures across the fleet,
    # one unit is fully replaced.
    num_replacements = (
        int(math.floor(expected_failures / charger.replacement_threshold))
        if charger.replacement_threshold > 0 else 0
    )
    total_replacement_cost = num_replacements * charger.full_replacement_cost

    # ── Downtime & lost revenue (fleet-wide) ───────────────────────────
    total_downtime_hours = expected_failures * charger.mttr_hours

    # Revenue lost per hour of dock downtime:
    cycles_per_hour = (
        derived.cycles_per_day_per_dock / station.operating_hours_per_day
        if station.operating_hours_per_day > 0 else 0.0
    )
    # Revenue attributable to one cycle = price_per_swap / packs_per_vehicle
    revenue_per_cycle = (
        revenue.price_per_swap / vehicle.packs_per_vehicle
        if vehicle.packs_per_vehicle > 0 else 0.0
    )
    lost_revenue = total_downtime_hours * cycles_per_hour * revenue_per_cycle

    # ── Fleet purchase cost ────────────────────────────────────────────
    fleet_purchase_cost = charger.purchase_cost_per_slot * total_docks

    # ── Spare inventory (per station) ──────────────────────────────────
    fleet_spare_cost = charger.spare_inventory_cost * station.num_stations

    # ── Fleet TCO ──────────────────────────────────────────────────────
    total_tco = (
        fleet_purchase_cost
        + total_repair_cost
        + total_replacement_cost
        + lost_revenue
        + fleet_spare_cost
    )

    # ── Cycles actually served (fleet-wide) ────────────────────────────
    fleet_uptime_hours = fleet_operating_hours - total_downtime_hours
    fleet_cycles_served = (
        cycles_per_hour * fleet_uptime_hours
        if fleet_uptime_hours > 0 else 0.0
    )

    cost_per_cycle = total_tco / fleet_cycles_served if fleet_cycles_served > 0 else 0.0

    return ChargerTCOBreakdown(
        total_docks=total_docks,
        purchase_cost=round(fleet_purchase_cost, 2),
        scheduled_hours_per_year_per_dock=round(scheduled_hours_per_year_per_dock, 1),
        fleet_operating_hours=round(fleet_operating_hours, 1),
        availability=round(availability, 6),
        expected_failures_over_horizon=round(expected_failures, 2),
        total_repair_cost=round(total_repair_cost, 2),
        num_replacements=num_replacements,
        total_replacement_cost=round(total_replacement_cost, 2),
        total_downtime_hours=round(total_downtime_hours, 2),
        lost_revenue_from_downtime=round(lost_revenue, 2),
        spare_inventory_cost=round(fleet_spare_cost, 2),
        total_tco=round(total_tco, 2),
        cycles_served_over_horizon=round(fleet_cycles_served, 2),
        cost_per_cycle=round(cost_per_cycle, 4),
    )
