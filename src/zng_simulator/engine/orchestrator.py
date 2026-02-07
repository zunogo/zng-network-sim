"""Stochastic orchestrator — Phase 2 monthly simulation loop (§7).

Wires together the three stochastic sub-engines:
  1. Demand engine       — noisy swap-visit counts per month
  2. Degradation engine  — cohort SOH tracking → lumpy replacement CapEx
  3. Charger reliability  — per-dock Weibull/exponential failures

Each month follows this sequence:
  demand → degradation.step(cycles) → charger_reliability.step()
  → revenue − OpEx − CapEx = net_cash_flow

Monte-Carlo mode runs N independent simulations with different seeds
and aggregates P10/P50/P90 percentiles for investor-grade outputs.

Entry point: ``run_engine(scenario, charger)``
  - Routes to Phase 1 static engine when ``scenario.simulation.engine == "static"``
  - Routes to stochastic loop when ``engine == "stochastic"``
"""

from __future__ import annotations

import numpy as np

from zng_simulator.config.scenario import Scenario
from zng_simulator.config.charger import ChargerVariant
from zng_simulator.engine.derived import compute_derived_params
from zng_simulator.engine.charger_tco import compute_charger_tco
from zng_simulator.engine.pack_tco import compute_pack_tco
from zng_simulator.engine.cost_per_cycle import compute_cpc_waterfall
from zng_simulator.engine.cashflow import run_simulation  # Phase 1 fallback
from zng_simulator.engine.demand import generate_monthly_demand
from zng_simulator.engine.degradation import DegradationTracker
from zng_simulator.engine.charger_reliability import ChargerReliabilityTracker
from zng_simulator.models.results import (
    MonthlySnapshot,
    RunSummary,
    SimulationResult,
    MonteCarloSummary,
)


# ═══════════════════════════════════════════════════════════════════════════
# Public entry point
# ═══════════════════════════════════════════════════════════════════════════

def run_engine(scenario: Scenario, charger: ChargerVariant) -> SimulationResult:
    """Run the appropriate engine based on ``scenario.simulation.engine``.

    - ``"static"``      → Phase 1 deterministic engine (``cashflow.run_simulation``)
    - ``"stochastic"``  → Phase 2 stochastic engine with optional Monte Carlo

    Returns a fully-populated ``SimulationResult``.
    """
    if scenario.simulation.engine == "static":
        return run_simulation(scenario, charger)

    if scenario.simulation.monte_carlo_runs > 1:
        return _run_monte_carlo(scenario, charger)

    seed = scenario.simulation.random_seed if scenario.simulation.random_seed is not None else 42
    return _run_single_stochastic(scenario, charger, seed)


# ═══════════════════════════════════════════════════════════════════════════
# Single stochastic run
# ═══════════════════════════════════════════════════════════════════════════

def _run_single_stochastic(
    scenario: Scenario,
    charger: ChargerVariant,
    seed: int,
) -> SimulationResult:
    """Execute one stochastic simulation run.

    This is the core loop that replaces the Phase 1 static engine with:
      - Stochastic demand (Poisson/Gamma)
      - Cohort-based battery degradation (lumpy CapEx)
      - Per-dock charger failure simulation (Weibull/exponential)
    """
    v = scenario.vehicle
    p = scenario.pack
    st = scenario.station
    op = scenario.opex
    rev = scenario.revenue
    ch = scenario.chaos
    sim = scenario.simulation
    demand_cfg = scenario.demand

    rng = np.random.default_rng(seed)

    # ── Deterministic setup (same for every run) ────────────────────────
    derived = compute_derived_params(v, p, charger, st, ch, rev)
    tco = compute_charger_tco(charger, derived, v, rev, sim, st)

    # Initial CapEx
    per_station_capex = (
        st.cabinet_cost + st.site_prep_cost
        + st.grid_connection_cost + st.security_deposit
    )
    station_capex = per_station_capex * st.num_stations + st.software_cost
    charger_capex = charger.purchase_cost_per_slot * derived.total_docks
    initial_packs = derived.total_packs
    pack_capex = initial_packs * p.unit_cost
    total_initial_capex = station_capex + charger_capex + pack_capex

    # Deterministic references (for CPC waterfall)
    ptco = compute_pack_tco(p, derived, v, rev, sim, st, initial_packs)
    cpc = compute_cpc_waterfall(derived, p, charger, op, ch, st, v, tco, ptco)

    # ── Initialize stochastic engines ───────────────────────────────────
    degradation = DegradationTracker(p, ch, auto_replace=True)
    degradation.add_cohort(initial_packs, born_month=1)

    charger_rel = ChargerReliabilityTracker(
        charger, derived.total_docks, st.operating_hours_per_day, rng,
    )

    # ── Monthly loop ────────────────────────────────────────────────────
    months: list[MonthlySnapshot] = []
    cohort_history: list = []

    cumulative_cf = 0.0
    break_even_month: int | None = None

    total_revenue = 0.0
    total_opex_sum = 0.0
    total_capex_sum = total_initial_capex
    total_cycles_all = 0
    total_cpc_weighted = 0.0

    # Stochastic accumulators
    total_packs_retired = 0
    total_charger_failures = 0
    total_replacement_capex = 0.0
    total_salvage_credit = 0.0

    for m in range(1, sim.horizon_months + 1):
        fleet_size = rev.initial_fleet_size + rev.monthly_fleet_additions * (m - 1)

        # ── 1. Stochastic demand ────────────────────────────────────────
        swap_visits, total_cycles = generate_monthly_demand(
            demand_cfg, derived, fleet_size, m, v.packs_per_vehicle, rng,
        )

        # ── 2. Battery degradation (cohort tracker) ─────────────────────
        deg_result = degradation.step(month=m, total_fleet_cycles=total_cycles)

        # Lumpy replacement CapEx
        replacement_capex = deg_result.packs_retired * p.unit_cost
        salvage_credit = deg_result.packs_retired * p.second_life_salvage_value
        net_replacement_cost = replacement_capex - salvage_credit

        # ── 3. Charger reliability ──────────────────────────────────────
        char_result = charger_rel.step(month=m)

        # ── 4. Revenue — per VISIT (per vehicle) ───────────────────────
        monthly_revenue = swap_visits * rev.price_per_swap

        # ── 5. OpEx ─────────────────────────────────────────────────────
        station_opex = (
            op.rent_per_month_per_station
            + op.auxiliary_power_per_month
            + op.preventive_maintenance_per_month_per_station
            + op.corrective_maintenance_per_month_per_station
            + op.insurance_per_month_per_station
            + op.logistics_per_month_per_station
        ) * st.num_stations

        energy_per_cycle_kwh = (
            p.nominal_capacity_kwh / charger.charging_efficiency_pct
            if charger.charging_efficiency_pct > 0 else 0.0
        )
        electricity_cost = total_cycles * energy_per_cycle_kwh * op.electricity_tariff_per_kwh
        labor_cost = total_cycles * op.pack_handling_labor_per_swap
        overhead = op.overhead_per_month
        sabotage_cost = ch.sabotage_pct_per_month * degradation.active_pack_count * p.unit_cost

        # Charger repair costs → operational (per event, stochastic)
        monthly_opex = (
            station_opex + electricity_cost + labor_cost
            + overhead + sabotage_cost + char_result.repair_cost
        )

        # ── 6. CapEx ────────────────────────────────────────────────────
        capex_this_month = 0.0
        if m == 1:
            capex_this_month = total_initial_capex

        # New vehicles → new packs
        if m > 1 and rev.monthly_fleet_additions > 0:
            new_packs = v.packs_per_vehicle * rev.monthly_fleet_additions
            capex_this_month += new_packs * p.unit_cost
            degradation.add_cohort(new_packs, born_month=m)

        # Lumpy pack replacement (the key Phase 2 fix!)
        capex_this_month += net_replacement_cost

        # Charger full replacements
        capex_this_month += char_result.replacement_cost

        # ── 7. Net cash flow ────────────────────────────────────────────
        net_cf = monthly_revenue - monthly_opex - capex_this_month
        cumulative_cf += net_cf

        if break_even_month is None and cumulative_cf >= 0 and m > 1:
            break_even_month = m

        # Accumulators
        total_revenue += monthly_revenue
        total_opex_sum += monthly_opex
        if m > 1:
            total_capex_sum += capex_this_month
        total_cycles_all += total_cycles
        total_cpc_weighted += cpc.total * total_cycles
        total_packs_retired += deg_result.packs_retired
        total_charger_failures += char_result.failures
        total_replacement_capex += replacement_capex
        total_salvage_credit += salvage_credit

        # ── 8. Record snapshot ──────────────────────────────────────────
        cohort_history.append(deg_result.cohort_snapshots)

        months.append(MonthlySnapshot(
            month=m,
            fleet_size=fleet_size,
            swap_visits=swap_visits,
            total_cycles=total_cycles,
            revenue=round(monthly_revenue, 2),
            opex_total=round(monthly_opex, 2),
            capex_this_month=round(capex_this_month, 2),
            net_cash_flow=round(net_cf, 2),
            cumulative_cash_flow=round(cumulative_cf, 2),
            cost_per_cycle=cpc,
            # Phase 2 stochastic fields
            avg_soh=deg_result.avg_soh,
            packs_retired_this_month=deg_result.packs_retired,
            packs_replaced_this_month=deg_result.packs_replaced,
            replacement_capex_this_month=round(net_replacement_cost, 2),
            salvage_credit_this_month=round(salvage_credit, 2),
            charger_failures_this_month=char_result.failures,
        ))

    # ── Build summary ───────────────────────────────────────────────────
    avg_cpc = total_cpc_weighted / total_cycles_all if total_cycles_all > 0 else 0.0
    last_soh = months[-1].avg_soh if months else None

    summary = RunSummary(
        charger_variant_name=charger.name,
        total_revenue=round(total_revenue, 2),
        total_opex=round(total_opex_sum, 2),
        total_capex=round(total_capex_sum, 2),
        total_net_cash_flow=round(total_revenue - total_opex_sum - total_capex_sum, 2),
        avg_cost_per_cycle=round(avg_cpc, 4),
        break_even_month=break_even_month,
        # Phase 2 summary fields
        total_packs_retired=total_packs_retired,
        total_charger_failures=total_charger_failures,
        mean_soh_at_end=last_soh,
        total_replacement_capex=round(total_replacement_capex, 2),
        total_salvage_credit=round(total_salvage_credit, 2),
    )

    return SimulationResult(
        scenario_id="default",
        charger_variant_id=charger.name,
        engine_type="stochastic",
        months=months,
        summary=summary,
        derived=derived,
        cpc_waterfall=cpc,
        charger_tco=tco,
        pack_tco=ptco,
        cohort_history=cohort_history,
    )


# ═══════════════════════════════════════════════════════════════════════════
# Monte-Carlo aggregation
# ═══════════════════════════════════════════════════════════════════════════

def _run_monte_carlo(
    scenario: Scenario,
    charger: ChargerVariant,
) -> SimulationResult:
    """Run N stochastic simulations and aggregate into P10/P50/P90.

    Strategy:
      1. Run N simulations with sequential seeds (base_seed + i)
      2. Collect RunSummary from each
      3. Compute MonteCarloSummary with percentiles
      4. Re-run the median simulation to get the representative full result
      5. Attach MonteCarloSummary to the representative result
    """
    base_seed = scenario.simulation.random_seed if scenario.simulation.random_seed is not None else 42
    num_runs = scenario.simulation.monte_carlo_runs

    # ── Collect summaries ───────────────────────────────────────────────
    summaries: list[RunSummary] = []
    for i in range(num_runs):
        result = _run_single_stochastic(scenario, charger, base_seed + i)
        summaries.append(result.summary)

    # ── Percentile arrays ───────────────────────────────────────────────
    ncfs = np.array([s.total_net_cash_flow for s in summaries])
    cpcs = np.array([s.avg_cost_per_cycle for s in summaries])
    retired = np.array([s.total_packs_retired or 0 for s in summaries])
    failures = np.array([s.total_charger_failures or 0 for s in summaries])
    fts = np.array([s.total_failure_to_serve or 0 for s in summaries])

    be_months = [s.break_even_month for s in summaries if s.break_even_month is not None]
    be_arr = np.array(be_months) if be_months else None

    mc = MonteCarloSummary(
        num_runs=num_runs,
        ncf_p10=float(np.percentile(ncfs, 10)),
        ncf_p50=float(np.percentile(ncfs, 50)),
        ncf_p90=float(np.percentile(ncfs, 90)),
        break_even_p10=int(np.percentile(be_arr, 10)) if be_arr is not None else None,
        break_even_p50=int(np.percentile(be_arr, 50)) if be_arr is not None else None,
        break_even_p90=int(np.percentile(be_arr, 90)) if be_arr is not None else None,
        cpc_p10=float(np.percentile(cpcs, 10)),
        cpc_p50=float(np.percentile(cpcs, 50)),
        cpc_p90=float(np.percentile(cpcs, 90)),
        avg_packs_retired=float(retired.mean()),
        max_packs_retired=int(retired.max()),
        avg_charger_failures=float(failures.mean()),
        avg_failure_to_serve=float(fts.mean()),
        max_failure_to_serve=int(fts.max()),
    )

    # ── Find & re-run the median run ────────────────────────────────────
    median_idx = int(np.argmin(np.abs(ncfs - mc.ncf_p50)))
    representative = _run_single_stochastic(scenario, charger, base_seed + median_idx)

    # Attach Monte-Carlo summary to the representative result
    return representative.model_copy(update={"monte_carlo": mc})
