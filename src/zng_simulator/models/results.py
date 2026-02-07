"""Result types — the contract between engine, finance, and dashboard."""

from __future__ import annotations

from pydantic import BaseModel


class DerivedParams(BaseModel):
    """Computed once from vehicle + pack + charger + station inputs (§6.1)."""

    # --- Energy per swap cycle ---
    energy_per_swap_cycle_per_pack_kwh: float
    """Energy a driver actually uses from one pack before swapping.
    = pack_capacity × (1 − range_anxiety_buffer).
    This is a driver-behavior assumption (they swap at ~20% SoC), not a hard limit."""

    energy_per_swap_cycle_per_vehicle_kwh: float
    """Total energy refilled per swap visit = packs_per_vehicle × energy_per_swap_cycle_per_pack."""

    total_energy_per_vehicle_kwh: float
    """Nameplate total: packs_per_vehicle × pack_capacity."""

    daily_energy_need_wh: float
    """Daily energy consumption = avg_daily_km × Wh_per_km."""

    # --- Swap visits & cycles ---
    swap_visits_per_vehicle_per_day: float
    """How many times a vehicle visits a station per day.
    = daily_energy_need / energy_per_swap_cycle_per_vehicle.
    One visit = all packs swapped."""

    # --- Charger / dock ---
    charge_time_minutes: float
    effective_c_rate: float
    cycles_per_day_per_dock: float

    # --- Pack ---
    pack_lifetime_cycles: int

    # --- Network ---
    total_docks: int
    cycles_per_month_per_station: float
    total_network_cycles_per_month: float

    # --- Fleet inventory ---
    initial_fleet_size: int
    """Number of vehicles at month 1."""
    packs_on_vehicles: int
    """initial_fleet_size × packs_per_vehicle — packs riding on vehicles."""
    packs_in_docks: int
    """total_docks — packs sitting in charger docks = the float / buffer inventory."""
    total_packs: int
    """packs_on_vehicles + packs_in_docks."""


class ChargerTCOBreakdown(BaseModel):
    """Fleet-level charger TCO over the simulation horizon (§6.3).

    MTBF is a **population / statistical** measure.  All failure, repair,
    replacement, and downtime metrics are computed across the entire charger
    fleet (total_docks), *not* per individual slot.

    Key formula:
      fleet_operating_hours = hours/day × 365 × years × total_docks
      expected_failures     = fleet_operating_hours / MTBF
      replacements          = floor(expected_failures / threshold)
    """

    total_docks: int
    """Total charger slots in the fleet (stations × docks_per_station)."""

    purchase_cost: float
    """Fleet purchase cost = total_docks × cost_per_slot."""

    scheduled_hours_per_year_per_dock: float
    """Reference: hours/day × 365 for one dock."""

    fleet_operating_hours: float
    """Total fleet operating hours over the full horizon
    = scheduled_hours_per_year_per_dock × years × total_docks."""

    availability: float
    """MTBF / (MTBF + MTTR) — steady-state statistical availability."""

    expected_failures_over_horizon: float
    """Fleet-wide expected failures = fleet_operating_hours / MTBF."""

    total_repair_cost: float
    """Fleet-wide: failures × repair_cost_per_event."""

    num_replacements: int
    """Fleet-wide: floor(failures / replacement_threshold)."""

    total_replacement_cost: float
    """Fleet-wide: replacements × full_replacement_cost."""

    total_downtime_hours: float
    """Fleet-wide: failures × MTTR."""

    lost_revenue_from_downtime: float
    """Revenue lost during fleet-wide downtime."""

    spare_inventory_cost: float
    """Spare capital = per-station spare cost × num_stations."""

    total_tco: float
    """Fleet-level total cost of ownership."""

    cycles_served_over_horizon: float
    """Fleet-wide cycles served (scheduled − downtime)."""

    cost_per_cycle: float
    """Fleet TCO / fleet cycles served — the number used in CPC waterfall."""


class PackTCOBreakdown(BaseModel):
    """Fleet-level battery pack failure TCO over the simulation horizon.

    Covers random / unexpected failures (BMS faults, cell swelling,
    connector damage) — separate from cycle-degradation.

    MTBF is a population statistic.  All metrics are fleet-level.

    Key formula:
      fleet_operating_hours = operating_hours_per_day × 365 × years × total_packs
      expected_failures     = fleet_operating_hours / MTBF
      replacements          = floor(expected_failures / threshold)
    """

    total_packs: int
    """Total packs in the fleet (vehicles × packs + docks + float)."""

    fleet_operating_hours: float
    """Total fleet hours = hrs/day × 365 × years × total_packs."""

    availability: float
    """MTBF / (MTBF + MTTR) — steady-state statistical availability."""

    expected_failures: float
    """Fleet-wide expected failures = fleet_operating_hours / MTBF."""

    total_repair_cost: float
    """Fleet-wide: failures × repair_cost_per_event."""

    num_replacements: int
    """Fleet-wide: floor(failures / replacement_threshold)."""

    total_replacement_cost: float
    """Fleet-wide: replacements × full_replacement_cost."""

    total_downtime_hours: float
    """Fleet-wide: failures × MTTR."""

    lost_revenue_from_downtime: float
    """Revenue lost while packs are down."""

    spare_inventory_cost: float
    """Spare pack capital = per-station cost × num_stations."""

    total_failure_tco: float
    """Total failure-related costs (excludes purchase — that's in degradation)."""

    failure_cost_per_cycle: float
    """Failure TCO / fleet cycles — added to the CPC battery component."""


class CostPerCycleWaterfall(BaseModel):
    """The 9-component CPC breakdown — each field is ₹/cycle (§6.4).
    'Cycle' = one pack charge-discharge cycle.
    Battery = degradation + failure costs."""

    battery: float
    charger: float
    electricity: float
    real_estate: float
    maintenance: float
    insurance: float
    sabotage: float
    logistics: float
    overhead: float
    total: float


class MonthlySnapshot(BaseModel):
    """One month of simulated operations."""

    month: int
    fleet_size: int
    swap_visits: int
    """Vehicle visits to stations (1 visit = all packs swapped)."""
    total_cycles: int
    """Pack charge-discharge cycles = swap_visits × packs_per_vehicle."""
    revenue: float
    opex_total: float
    capex_this_month: float
    net_cash_flow: float
    cumulative_cash_flow: float
    cost_per_cycle: CostPerCycleWaterfall


class RunSummary(BaseModel):
    """Aggregated KPIs for one full simulation run."""

    charger_variant_name: str
    total_revenue: float
    total_opex: float
    total_capex: float
    total_net_cash_flow: float
    avg_cost_per_cycle: float
    break_even_month: int | None  # None if never breaks even


class SimulationResult(BaseModel):
    """Complete output of one engine run (one vehicle + pack + charger combo)."""

    scenario_id: str
    charger_variant_id: str
    engine_type: str  # "static" for Phase 1
    months: list[MonthlySnapshot]
    summary: RunSummary
    derived: DerivedParams
    cpc_waterfall: CostPerCycleWaterfall
    charger_tco: ChargerTCOBreakdown
    pack_tco: PackTCOBreakdown