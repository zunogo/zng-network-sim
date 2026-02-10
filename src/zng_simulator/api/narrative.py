"""Narrative generator — plain-English interpretation of simulation results.

Converts raw ``SimulationResult`` into structured, LLM-friendly text
that explains the business model outcome, key risks, and recommended actions.
"""

from __future__ import annotations

from zng_simulator.models.results import SimulationResult


def generate_narrative(result: SimulationResult) -> str:
    """Generate a plain-English narrative from a simulation result.

    Returns a structured text block covering:
      1. Business model summary
      2. Unit economics verdict
      3. Financial health
      4. Risk factors
      5. Recommendations
    """
    s = result.summary
    d = result.derived
    w = result.cpc_waterfall
    months = result.months

    # -- Revenue per swap --
    if months:
        last_month = months[-1]
        fleet = last_month.fleet_size
        revenue_per_swap = last_month.revenue / max(last_month.swap_visits, 1)
    else:
        fleet = d.initial_fleet_size
        revenue_per_swap = 0

    # -- Unit economics --
    margin_per_swap = revenue_per_swap - (w.total * 1)  # CPC is per cycle, 1 cycle ~ 1 pack
    margin_sign = "POSITIVE" if margin_per_swap > 0 else "NEGATIVE"

    # -- Top cost drivers (sorted) --
    cost_components = [
        ("Battery (degradation + failures)", w.battery),
        ("Charger (TCO amortized)", w.charger),
        ("Electricity", w.electricity),
        ("Real estate", w.real_estate),
        ("Maintenance", w.maintenance),
        ("Insurance", w.insurance),
        ("Sabotage / loss", w.sabotage),
        ("Logistics / rebalancing", w.logistics),
        ("Overhead", w.overhead),
    ]
    cost_components.sort(key=lambda x: x[1], reverse=True)
    top3 = cost_components[:3]

    sections: list[str] = []

    # ── 1. Business model summary ──
    sections.append("=" * 60)
    sections.append("BUSINESS MODEL SUMMARY")
    sections.append("=" * 60)
    sections.append(
        f"Charger variant: {s.charger_variant_name}\n"
        f"Engine: {result.engine_type}\n"
        f"Horizon: {len(months)} months\n"
        f"Fleet at end: {fleet} vehicles\n"
        f"Total packs: {d.total_packs}\n"
        f"Total docks: {d.total_docks}\n"
        f"Swaps per vehicle per day: {d.swap_visits_per_vehicle_per_day:.2f}\n"
        f"Charge time per pack: {d.charge_time_minutes:.1f} minutes\n"
        f"Pack lifetime: {d.pack_lifetime_cycles} cycles"
    )

    # ── 2. Unit economics ──
    sections.append("")
    sections.append("=" * 60)
    sections.append("UNIT ECONOMICS")
    sections.append("=" * 60)
    sections.append(
        f"Fully-loaded cost per cycle: ₹{w.total:.2f}\n"
        f"Revenue per swap (approx): ₹{revenue_per_swap:.2f}\n"
        f"Gross margin per cycle: ₹{margin_per_swap:.2f} ({margin_sign})\n"
        f"\nCost breakdown (₹/cycle, largest first):"
    )
    for name, val in cost_components:
        pct = (val / w.total * 100) if w.total > 0 else 0
        sections.append(f"  {name:40s}  ₹{val:8.2f}  ({pct:5.1f}%)")

    sections.append(
        f"\nTop 3 cost drivers account for "
        f"{sum(c[1] for c in top3) / max(w.total, 0.01) * 100:.0f}% of total CPC."
    )

    # ── 3. Financial health ──
    sections.append("")
    sections.append("=" * 60)
    sections.append("FINANCIAL HEALTH")
    sections.append("=" * 60)

    be = s.break_even_month
    sections.append(
        f"Total revenue: ₹{s.total_revenue:,.0f}\n"
        f"Total OpEx: ₹{s.total_opex:,.0f}\n"
        f"Total CapEx: ₹{s.total_capex:,.0f}\n"
        f"Net cash flow: ₹{s.total_net_cash_flow:,.0f}\n"
        f"Break-even month: {be if be else 'NEVER (within horizon)'}"
    )

    if result.dcf:
        dcf = result.dcf
        sections.append(
            f"\nNPV: ₹{dcf.npv:,.0f}\n"
            f"IRR: {dcf.irr * 100:.1f}%" if dcf.irr else f"\nNPV: ₹{dcf.npv:,.0f}\nIRR: N/A (no positive root)"
        )
        sections.append(
            f"Discounted payback: month {dcf.discounted_payback_month}"
            if dcf.discounted_payback_month
            else "Discounted payback: NEVER"
        )

    if result.dscr:
        dscr = result.dscr
        sections.append(
            f"\nDSCR average: {dscr.avg_dscr:.2f}\n"
            f"DSCR minimum: {dscr.min_dscr:.2f} (month {dscr.min_dscr_month})\n"
            f"Covenant threshold: {dscr.covenant_threshold:.2f}\n"
            f"Breach months: {len(dscr.breach_months)} months below covenant"
        )

    # ── 4. Monte Carlo (if available) ──
    if result.monte_carlo:
        mc = result.monte_carlo
        sections.append("")
        sections.append("=" * 60)
        sections.append("MONTE CARLO UNCERTAINTY")
        sections.append("=" * 60)
        sections.append(
            f"Runs: {mc.num_runs}\n"
            f"Net cash flow — P10: ₹{mc.ncf_p10:,.0f} | P50: ₹{mc.ncf_p50:,.0f} | P90: ₹{mc.ncf_p90:,.0f}\n"
            f"CPC — P10: ₹{mc.cpc_p10:.2f} | P50: ₹{mc.cpc_p50:.2f} | P90: ₹{mc.cpc_p90:.2f}\n"
            f"Break-even — P10: {mc.break_even_p10} | P50: {mc.break_even_p50} | P90: {mc.break_even_p90}\n"
            f"Avg packs retired: {mc.avg_packs_retired:.0f} | Max: {mc.max_packs_retired}\n"
            f"Avg charger failures: {mc.avg_charger_failures:.0f}\n"
            f"Avg unserved demand events: {mc.avg_failure_to_serve:.0f}"
        )
        spread = mc.ncf_p90 - mc.ncf_p10
        sections.append(
            f"\nP10-P90 spread: ₹{spread:,.0f} — "
            f"{'Wide uncertainty — results sensitive to stochastic inputs' if abs(spread) > abs(mc.ncf_p50) * 0.5 else 'Moderate uncertainty — results relatively stable'}"
        )

    # ── 5. Stochastic details ──
    if result.engine_type == "stochastic" and s.total_packs_retired is not None:
        sections.append("")
        sections.append("=" * 60)
        sections.append("OPERATIONAL RISK")
        sections.append("=" * 60)
        sections.append(
            f"Total packs retired: {s.total_packs_retired}\n"
            f"Total replacement CapEx: ₹{s.total_replacement_capex:,.0f}" if s.total_replacement_capex else
            f"Total packs retired: {s.total_packs_retired}"
        )
        if s.total_charger_failures is not None:
            sections.append(f"Total charger failures: {s.total_charger_failures}")
        if s.total_failure_to_serve is not None:
            sections.append(f"Total unserved demand events: {s.total_failure_to_serve}")
        if s.mean_soh_at_end is not None:
            sections.append(f"Fleet avg SOH at end: {s.mean_soh_at_end * 100:.1f}%")

    # ── 6. Recommendations ──
    sections.append("")
    sections.append("=" * 60)
    sections.append("RECOMMENDATIONS")
    sections.append("=" * 60)

    recs: list[str] = []
    if margin_per_swap < 0:
        recs.append(
            f"Unit economics are NEGATIVE (₹{margin_per_swap:.2f}/cycle). "
            f"Top cost driver is '{top3[0][0]}' at ₹{top3[0][1]:.2f}/cycle. "
            f"Consider: reducing {top3[0][0].lower().split('(')[0].strip()} costs, increasing price per swap, or scaling fleet to dilute fixed costs."
        )
    else:
        recs.append(f"Unit economics are positive at ₹{margin_per_swap:.2f}/cycle gross margin.")

    if be is None:
        recs.append("Project does NOT break even within the horizon. Consider extending horizon, reducing CapEx, or increasing fleet growth.")
    elif be > 36:
        recs.append(f"Break-even at month {be} is late. Investors may want faster payback.")

    if result.dscr and result.dscr.min_dscr < result.dscr.covenant_threshold:
        recs.append(
            f"DSCR breaches covenant ({result.dscr.min_dscr:.2f} < {result.dscr.covenant_threshold:.2f}) "
            f"in {len(result.dscr.breach_months)} months. Debt may not be serviceable. Consider lower leverage or longer grace period."
        )

    if not recs:
        recs.append("No critical issues identified. Run sensitivity analysis to test robustness.")

    for i, rec in enumerate(recs, 1):
        sections.append(f"  {i}. {rec}")

    return "\n".join(sections)


def generate_comparison_narrative(results: list[SimulationResult]) -> str:
    """Generate comparison narrative across charger variants."""
    if len(results) < 2:
        return generate_narrative(results[0]) if results else "No results to compare."

    sections: list[str] = []
    sections.append("=" * 60)
    sections.append("CHARGER VARIANT COMPARISON")
    sections.append("=" * 60)
    sections.append(f"Comparing {len(results)} charger variants:\n")

    # Collect comparison data
    variants: list[dict] = []
    for r in results:
        variants.append({
            "name": r.summary.charger_variant_name,
            "cpc": r.cpc_waterfall.total,
            "cpc_charger": r.cpc_waterfall.charger,
            "ncf": r.summary.total_net_cash_flow,
            "be": r.summary.break_even_month,
            "npv": r.dcf.npv if r.dcf else None,
        })

    # Sort by CPC (best first)
    variants.sort(key=lambda v: v["cpc"])

    header = f"{'Variant':25s}  {'CPC':>10s}  {'Charger CPC':>12s}  {'NCF':>14s}  {'Break-even':>10s}  {'NPV':>14s}"
    sections.append(header)
    sections.append("-" * len(header))
    for v in variants:
        npv_str = f"₹{v['npv']:>12,.0f}" if v["npv"] is not None else f"{'N/A':>14s}"
        be_str = f"{v['be']:>10d}" if v["be"] else f"{'Never':>10s}"
        sections.append(
            f"{v['name']:25s}  ₹{v['cpc']:>8.2f}  ₹{v['cpc_charger']:>10.2f}  ₹{v['ncf']:>12,.0f}  {be_str}  {npv_str}"
        )

    best = variants[0]
    worst = variants[-1]
    sections.append(f"\nBest option: {best['name']} (lowest CPC at ₹{best['cpc']:.2f}/cycle)")

    if len(variants) > 1:
        saving = worst["cpc"] - best["cpc"]
        sections.append(
            f"Saves ₹{saving:.2f}/cycle vs {worst['name']}."
        )

    return "\n".join(sections)
