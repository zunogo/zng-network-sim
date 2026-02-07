"""Monthly cash flow simulation — Phase 1 static engine.

Key distinction:
  - swap_visit = one vehicle arrives, ALL its packs are swapped. Revenue is per visit.
  - cycle = one pack charge-discharge. Costs (electricity, degradation) are per cycle.
  - total_cycles = swap_visits × packs_per_vehicle
"""

from __future__ import annotations

import math

from zng_simulator.config.scenario import Scenario
from zng_simulator.config.charger import ChargerVariant
from zng_simulator.engine.derived import compute_derived_params
from zng_simulator.engine.charger_tco import compute_charger_tco
from zng_simulator.engine.pack_tco import compute_pack_tco
from zng_simulator.engine.cost_per_cycle import compute_cpc_waterfall
from zng_simulator.models.results import (
    MonthlySnapshot,
    RunSummary,
    SimulationResult,
)


def run_simulation(scenario: Scenario, charger: ChargerVariant) -> SimulationResult:
    """Run one deterministic simulation for a specific charger variant.

    Returns a full SimulationResult with monthly snapshots and summary.
    """
    v = scenario.vehicle
    p = scenario.pack
    st = scenario.station
    op = scenario.opex
    rev = scenario.revenue
    ch = scenario.chaos
    sim = scenario.simulation

    # --- Derived parameters ---
    derived = compute_derived_params(v, p, charger, st, ch, rev)

    # --- Charger TCO ---
    tco = compute_charger_tco(charger, derived, v, rev, sim, st)

    # --- Initial CapEx (month 0) ---
    per_station_capex = (
        st.cabinet_cost + st.site_prep_cost + st.grid_connection_cost + st.security_deposit
    )
    station_capex = per_station_capex * st.num_stations + st.software_cost

    total_docks = derived.total_docks
    charger_capex = charger.purchase_cost_per_slot * total_docks

    # Initial pack inventory from derived (vehicles + docks + float)
    initial_packs = derived.total_packs
    pack_capex = initial_packs * p.unit_cost

    total_initial_capex = station_capex + charger_capex + pack_capex

    # --- Pack TCO (fleet-level failure costs) ---
    ptco = compute_pack_tco(p, derived, v, rev, sim, st, initial_packs)

    # --- Cost per cycle waterfall (steady-state) ---
    cpc = compute_cpc_waterfall(derived, p, charger, op, ch, st, v, tco, ptco)

    # --- Monthly loop ---
    months: list[MonthlySnapshot] = []
    cumulative_cf = 0.0
    break_even_month: int | None = None
    total_revenue = 0.0
    total_opex_sum = 0.0
    total_capex_sum = total_initial_capex
    total_cycles_all = 0
    total_cpc_weighted = 0.0

    for m in range(1, sim.horizon_months + 1):
        fleet_size = rev.initial_fleet_size + rev.monthly_fleet_additions * (m - 1)

        # ── Swap visits & cycles ──────────────────────────────────────
        visits_per_day = derived.swap_visits_per_vehicle_per_day * fleet_size
        swap_visits = int(round(visits_per_day * 30))

        # Each visit swaps ALL packs → that many charge-discharge cycles
        total_cycles = swap_visits * v.packs_per_vehicle

        # ── Revenue — per VISIT (per vehicle), not per pack ───────────
        monthly_revenue = swap_visits * rev.price_per_swap

        # ── OpEx ──────────────────────────────────────────────────────
        # Station-level fixed costs
        station_opex = (
            op.rent_per_month_per_station
            + op.auxiliary_power_per_month
            + op.preventive_maintenance_per_month_per_station
            + op.corrective_maintenance_per_month_per_station
            + op.insurance_per_month_per_station
            + op.logistics_per_month_per_station
        ) * st.num_stations

        # Electricity — per cycle (each pack charged)
        energy_per_cycle_kwh = (
            p.nominal_capacity_kwh / charger.charging_efficiency_pct
            if charger.charging_efficiency_pct > 0 else 0.0
        )
        electricity_cost = total_cycles * energy_per_cycle_kwh * op.electricity_tariff_per_kwh

        # Pack handling labor — per pack swapped (= per cycle)
        labor_cost = total_cycles * op.pack_handling_labor_per_swap

        # Overhead
        overhead = op.overhead_per_month

        # Sabotage
        sabotage_cost = ch.sabotage_pct_per_month * initial_packs * p.unit_cost

        monthly_opex = station_opex + electricity_cost + labor_cost + overhead + sabotage_cost

        # ── CapEx this month ──────────────────────────────────────────
        capex_this_month = 0.0
        if m == 1:
            capex_this_month = total_initial_capex

        # Packs for new vehicles
        if m > 1 and rev.monthly_fleet_additions > 0:
            new_packs = v.packs_per_vehicle * rev.monthly_fleet_additions
            capex_this_month += new_packs * p.unit_cost

        # Charger repair/replace spread evenly (TCO is already fleet-level)
        if tco.expected_failures_over_horizon > 0 and sim.horizon_months > 0:
            monthly_charger_repair_cost = tco.total_repair_cost / sim.horizon_months
            monthly_charger_replace_cost = tco.total_replacement_cost / sim.horizon_months
            capex_this_month += monthly_charger_repair_cost + monthly_charger_replace_cost

        # Pack repair/replace spread evenly (fleet-level)
        if ptco.expected_failures > 0 and sim.horizon_months > 0:
            monthly_pack_repair_cost = ptco.total_repair_cost / sim.horizon_months
            monthly_pack_replace_cost = ptco.total_replacement_cost / sim.horizon_months
            capex_this_month += monthly_pack_repair_cost + monthly_pack_replace_cost

        # ── Net cash flow ─────────────────────────────────────────────
        net_cf = monthly_revenue - monthly_opex - capex_this_month
        cumulative_cf += net_cf

        if break_even_month is None and cumulative_cf >= 0 and m > 1:
            break_even_month = m

        total_revenue += monthly_revenue
        total_opex_sum += monthly_opex
        if m > 1:
            total_capex_sum += capex_this_month
        total_cycles_all += total_cycles
        total_cpc_weighted += cpc.total * total_cycles

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
        ))

    # --- Summary ---
    avg_cpc = total_cpc_weighted / total_cycles_all if total_cycles_all > 0 else 0.0

    summary = RunSummary(
        charger_variant_name=charger.name,
        total_revenue=round(total_revenue, 2),
        total_opex=round(total_opex_sum, 2),
        total_capex=round(total_capex_sum, 2),
        total_net_cash_flow=round(total_revenue - total_opex_sum - total_capex_sum, 2),
        avg_cost_per_cycle=round(avg_cpc, 4),
        break_even_month=break_even_month,
    )

    return SimulationResult(
        scenario_id="default",
        charger_variant_id=charger.name,
        engine_type="static",
        months=months,
        summary=summary,
        derived=derived,
        cpc_waterfall=cpc,
        charger_tco=tco,
        pack_tco=ptco,
    )
