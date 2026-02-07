"""Result types — the contract between engine, finance, and dashboard.

Phase 1 (static engine) produces deterministic results.
Phase 2 (stochastic engine) adds optional fields for degradation cohorts,
charger failure events, demand noise, and SLA metrics.  All Phase 2 fields
default to ``None`` so that Phase 1 code never breaks.
"""

from __future__ import annotations

from pydantic import BaseModel


# ═══════════════════════════════════════════════════════════════════════════
# Derived operational parameters (Phase 1 — unchanged)
# ═══════════════════════════════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════════════════════════════
# Monthly snapshot (shared by both engines)
# ═══════════════════════════════════════════════════════════════════════════

class MonthlySnapshot(BaseModel):
    """One month of simulated operations.

    Phase 1 (static) fills the core fields; Phase 2 optional fields stay None.
    Phase 2 (stochastic) populates everything.
    """

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

    # --- Phase 2: stochastic fields (optional, None in static mode) ---
    avg_soh: float | None = None
    """Average State-of-Health across all active pack cohorts (0–1)."""

    packs_retired_this_month: int | None = None
    """Packs retired due to SOH hitting retirement threshold this month."""

    packs_replaced_this_month: int | None = None
    """New packs purchased to replace retired packs this month."""

    replacement_capex_this_month: float | None = None
    """Lumpy CapEx from cohort retirements: retired × (unit_cost − salvage).
    This is the *actual* replacement cost — NOT spread evenly."""

    salvage_credit_this_month: float | None = None
    """Salvage value recovered from retired packs this month."""

    charger_failures_this_month: int | None = None
    """Charger failure events drawn from MTBF distribution this month."""

    failure_to_serve_count: int | None = None
    """Demand events that could not be served (no available dock/pack)."""

    avg_wait_time_minutes: float | None = None
    """Average wait time at station for vehicles seeking a swap."""


# ═══════════════════════════════════════════════════════════════════════════
# Run summary
# ═══════════════════════════════════════════════════════════════════════════

class RunSummary(BaseModel):
    """Aggregated KPIs for one full simulation run."""

    charger_variant_name: str
    total_revenue: float
    total_opex: float
    total_capex: float
    total_net_cash_flow: float
    avg_cost_per_cycle: float
    break_even_month: int | None  # None if never breaks even

    # --- Phase 2: stochastic summary (optional) ---
    total_packs_retired: int | None = None
    """Total packs retired over the horizon (all cohorts)."""

    total_charger_failures: int | None = None
    """Total charger failure events over the horizon."""

    total_failure_to_serve: int | None = None
    """Total unserved demand events over the horizon."""

    mean_soh_at_end: float | None = None
    """Fleet-average SOH at the last month (0–1)."""

    total_replacement_capex: float | None = None
    """Sum of lumpy pack replacement CapEx over the horizon."""

    total_salvage_credit: float | None = None
    """Sum of salvage credits from retired packs."""


# ═══════════════════════════════════════════════════════════════════════════
# Cohort status (Phase 2 — tracks a batch of packs through their lifecycle)
# ═══════════════════════════════════════════════════════════════════════════

class CohortStatus(BaseModel):
    """Snapshot of one pack cohort at a given month.

    Used by the degradation engine to track SOH progression and
    trigger retirement when SOH ≤ threshold.
    """

    cohort_id: int
    """Monotonically increasing ID assigned at creation."""

    born_month: int
    """Month this cohort was created (1-indexed)."""

    pack_count: int
    """Number of packs in this cohort (at birth, before any retirement)."""

    current_soh: float
    """Current state-of-health (0–1). Starts at 1.0."""

    cumulative_cycles: int
    """Total charge-discharge cycles accumulated by this cohort."""

    is_retired: bool
    """True if SOH ≤ retirement threshold → removed from active fleet."""

    retired_month: int | None = None
    """Month when retired (None if still active)."""


# ═══════════════════════════════════════════════════════════════════════════
# Monte-Carlo aggregate (Phase 2 — summarises multiple stochastic runs)
# ═══════════════════════════════════════════════════════════════════════════

class MonteCarloSummary(BaseModel):
    """Aggregate statistics across N Monte-Carlo stochastic runs.

    Provides P10/P50/P90 percentiles for key financial metrics,
    giving investors confidence intervals instead of point estimates.
    """

    num_runs: int
    """Number of Monte-Carlo iterations completed."""

    # --- Net cash flow percentiles ---
    ncf_p10: float
    """10th percentile of total net cash flow (pessimistic)."""
    ncf_p50: float
    """50th percentile (median) of total net cash flow."""
    ncf_p90: float
    """90th percentile of total net cash flow (optimistic)."""

    # --- Break-even month percentiles ---
    break_even_p10: int | None
    """10th percentile break-even month (late break-even)."""
    break_even_p50: int | None
    """Median break-even month."""
    break_even_p90: int | None
    """90th percentile break-even month (early break-even)."""

    # --- CPC percentiles ---
    cpc_p10: float
    """10th percentile avg CPC (low cost — optimistic)."""
    cpc_p50: float
    """Median avg CPC."""
    cpc_p90: float
    """90th percentile avg CPC (high cost — pessimistic)."""

    # --- Pack retirement stats ---
    avg_packs_retired: float
    """Mean total packs retired across runs."""
    max_packs_retired: int
    """Worst-case packs retired in any single run."""

    # --- Charger failure stats ---
    avg_charger_failures: float
    """Mean total charger failures across runs."""

    # --- SLA stats ---
    avg_failure_to_serve: float
    """Mean unserved demand events across runs."""
    max_failure_to_serve: int
    """Worst-case unserved demand in any single run."""


# ═══════════════════════════════════════════════════════════════════════════
# Simulation result (shared top-level container)
# ═══════════════════════════════════════════════════════════════════════════

class SimulationResult(BaseModel):
    """Complete output of one engine run (one vehicle + pack + charger combo).

    For static engine: ``engine_type='static'``, stochastic fields are None.
    For stochastic engine: ``engine_type='stochastic'``, includes cohort data
    and optionally a Monte-Carlo summary.
    """

    scenario_id: str
    charger_variant_id: str
    engine_type: str  # "static" or "stochastic"
    months: list[MonthlySnapshot]
    summary: RunSummary
    derived: DerivedParams
    cpc_waterfall: CostPerCycleWaterfall
    charger_tco: ChargerTCOBreakdown
    pack_tco: PackTCOBreakdown

    # --- Phase 2: stochastic extras (optional) ---
    cohort_history: list[list[CohortStatus]] | None = None
    """Month-by-month cohort snapshots.  cohort_history[m] is a list of
    CohortStatus for each active/retired cohort at month m.
    None in static mode."""

    monte_carlo: MonteCarloSummary | None = None
    """Aggregate P10/P50/P90 across Monte-Carlo runs.
    None for single-run results (static or single stochastic run)."""

    # --- Phase 3: financial overlay (optional) ---
    dcf: "DCFResult | None" = None
    """DCF analysis computed by finance module. None until Phase 3 runs."""

    debt_schedule: "DebtSchedule | None" = None
    """Debt amortization schedule. None if no debt or Phase 3 not run."""

    dscr: "DSCRResult | None" = None
    """DSCR analysis. None until Phase 3 runs."""

    financial_statements: "FinancialStatements | None" = None
    """P&L and Cash Flow Statement. None until Phase 3 runs."""


# ═══════════════════════════════════════════════════════════════════════════
# Phase 3: Financial result types
# ═══════════════════════════════════════════════════════════════════════════

class MonthlyDCFRow(BaseModel):
    """One month's DCF calculation."""

    month: int
    discount_factor: float
    """1 / (1 + r_monthly)^month."""

    nominal_net_cf: float
    """Undiscounted net cash flow."""

    pv_net_cf: float
    """Present value of net cash flow."""

    cumulative_pv: float
    """Running sum of PV(net CF) from month 1 to this month."""


class DCFResult(BaseModel):
    """Full DCF analysis output."""

    npv: float
    """Net Present Value = Σ PV(CF_t) + PV(terminal_value)."""

    irr: float | None
    """Internal Rate of Return (annual). None if no real root."""

    discounted_payback_month: int | None
    """First month where cumulative PV(CF) ≥ 0. None if never."""

    terminal_value: float
    """Terminal / residual value at horizon end (PV terms)."""

    monthly_dcf: list[MonthlyDCFRow]
    """Per-month discount factors and PV cash flows."""

    undiscounted_total: float
    """Sum of nominal CFs (for comparison)."""


class DebtScheduleRow(BaseModel):
    """One month of the debt amortization schedule."""

    month: int
    opening_balance: float
    interest: float
    principal: float
    emi: float
    """Equal Monthly Installment (interest + principal). During grace period, principal = 0."""
    closing_balance: float


class DebtSchedule(BaseModel):
    """Full debt amortization schedule."""

    loan_amount: float
    """Initial loan = total_initial_capex × debt_pct_of_capex."""

    monthly_rate: float
    """Monthly interest rate = annual_rate / 12."""

    rows: list[DebtScheduleRow]
    """Month-by-month schedule."""

    total_interest_paid: float
    """Sum of all interest payments."""

    total_principal_paid: float
    """Sum of all principal payments (should equal loan_amount)."""


class DSCRResult(BaseModel):
    """Debt Service Coverage Ratio analysis."""

    monthly_dscr: list[float]
    """DSCR for each month: NOI / debt_service. Inf if no debt service."""

    avg_dscr: float
    """Average DSCR across all months with debt service > 0."""

    min_dscr: float
    """Minimum DSCR in any single month."""

    min_dscr_month: int
    """Month where minimum DSCR occurs."""

    breach_months: list[int]
    """Months where DSCR < covenant threshold."""

    covenant_threshold: float
    """The threshold used (from FinanceConfig)."""

    asset_cover_ratio: float | None = None
    """(Remaining asset value) / outstanding loan at horizon end."""


class MonthlyPnL(BaseModel):
    """Monthly Profit & Loss statement."""

    month: int
    revenue: float
    electricity_cost: float
    labor_cost: float
    gross_profit: float
    """Revenue − electricity − labor."""

    station_opex: float
    """Rent + maintenance + insurance + logistics + aux + overhead + sabotage."""

    ebitda: float
    """Gross profit − station_opex."""

    depreciation: float
    ebit: float
    """EBITDA − depreciation."""

    interest: float
    ebt: float
    """EBIT − interest."""

    tax: float
    net_income: float
    """EBT − tax (floored at 0 if loss → no tax)."""


class MonthlyCashFlowStatement(BaseModel):
    """Monthly Cash Flow Statement (3-part)."""

    month: int
    operating_cf: float
    """Revenue − cash OpEx (electricity + labor + station costs)."""

    investing_cf: float
    """−CapEx − pack/charger replacements."""

    financing_cf: float
    """Debt drawdown (month 1) − EMI repayments."""

    net_cf: float
    """Operating + Investing + Financing."""

    cumulative_cf: float


class FinancialStatements(BaseModel):
    """Container for monthly financial statements."""

    pnl: list[MonthlyPnL]
    cash_flow: list[MonthlyCashFlowStatement]