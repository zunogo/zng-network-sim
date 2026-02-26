"""Local tool executor — maps Claude tool calls to direct Python function invocations.

Replicates the helper patterns from ``api.server`` (deep merge, scenario building,
financial overlays) without importing the FastAPI app object.
"""

from __future__ import annotations

import json
from typing import Any

from zng_simulator.config.scenario import Scenario
from zng_simulator.config.charger import ChargerVariant
from zng_simulator.engine.orchestrator import run_engine
from zng_simulator.engine.optimizer import find_minimum_fleet_size
from zng_simulator.finance.dcf import build_dcf_table
from zng_simulator.finance.dscr import build_debt_schedule, compute_dscr
from zng_simulator.finance.statements import build_financial_statements
from zng_simulator.finance.sensitivity import run_sensitivity as _run_sensitivity
from zng_simulator.models.results import SimulationResult
from zng_simulator.api.context import build_context, get_default_scenario
from zng_simulator.api.narrative import generate_narrative, generate_comparison_narrative


# ═══════════════════════════════════════════════════════════════════════════
# Helpers (replicated from api.server to avoid importing FastAPI app)
# ═══════════════════════════════════════════════════════════════════════════

def _deep_merge(base: dict, overrides: dict) -> dict:
    """Recursively merge *overrides* into *base* dict (mutates *base*)."""
    for key, val in overrides.items():
        if key in base and isinstance(base[key], dict) and isinstance(val, dict):
            _deep_merge(base[key], val)
        else:
            base[key] = val
    return base


def _build_scenario(overrides: dict[str, Any]) -> Scenario:
    """Build a Scenario from partial overrides merged onto defaults."""
    defaults = get_default_scenario()
    _deep_merge(defaults, overrides)
    return Scenario(**defaults)


def attach_financials(
    result: SimulationResult,
    scenario: Scenario,
    charger: ChargerVariant,
) -> SimulationResult:
    """Attach financial overlays (DCF, DSCR, statements) to an existing result."""
    fin = scenario.finance
    sim = scenario.simulation
    total_capex = result.summary.total_capex
    salvage = result.derived.total_packs * scenario.pack.second_life_salvage_value

    try:
        result.dcf = build_dcf_table(
            result.months, result.summary, fin,
            sim.discount_rate_annual, salvage,
        )
    except Exception:
        pass

    debt_sched = None
    try:
        debt_sched = build_debt_schedule(total_capex, fin, sim.horizon_months)
        result.debt_schedule = debt_sched
        result.dscr = compute_dscr(result.months, debt_sched, fin)
    except Exception:
        pass

    try:
        if debt_sched is not None:
            result.financial_statements = build_financial_statements(
                result.months, debt_sched, fin,
                scenario.opex, scenario.station,
                scenario.pack, charger, total_capex,
            )
    except Exception:
        pass

    return result


def _run_with_financials(scenario: Scenario, charger: ChargerVariant) -> SimulationResult:
    """Run engine + attach financial overlays (DCF, DSCR, statements)."""
    result = run_engine(scenario, charger)
    return attach_financials(result, scenario, charger)


# ═══════════════════════════════════════════════════════════════════════════
# Result condensation (keep tool results small for Claude context)
# ═══════════════════════════════════════════════════════════════════════════

def condense_result(result: SimulationResult) -> dict:
    """Produce a token-efficient summary of SimulationResult for Claude."""
    d = result.model_dump()

    condensed: dict[str, Any] = {
        "summary": d["summary"],
        "cpc_waterfall": d["cpc_waterfall"],
    }

    # Key derived fields only
    derived = d.get("derived", {})
    condensed["derived"] = {
        k: derived[k]
        for k in [
            "swap_visits_per_vehicle_per_day",
            "charge_time_minutes",
            "total_packs",
            "total_docks",
            "initial_fleet_size",
            "pack_lifetime_cycles",
        ]
        if k in derived
    }

    # DCF top-level
    if d.get("dcf"):
        condensed["dcf"] = {
            k: d["dcf"][k]
            for k in ["npv", "irr", "discounted_payback_month", "terminal_value"]
            if k in d["dcf"]
        }

    # DSCR top-level
    if d.get("dscr"):
        condensed["dscr"] = {
            k: d["dscr"][k]
            for k in ["avg_dscr", "min_dscr", "min_dscr_month", "breach_months", "covenant_threshold"]
            if k in d["dscr"]
        }

    # Monte Carlo
    if d.get("monte_carlo"):
        condensed["monte_carlo"] = d["monte_carlo"]

    # First + last month snapshots only
    months = d.get("months", [])
    if months:
        condensed["months_sample"] = {
            "first": months[0],
            "last": months[-1],
            "count": len(months),
        }

    return condensed


# ═══════════════════════════════════════════════════════════════════════════
# Main dispatch
# ═══════════════════════════════════════════════════════════════════════════

def execute_tool(
    tool_name: str,
    tool_input: dict,
) -> tuple[dict, SimulationResult | list[SimulationResult] | None]:
    """Execute a simulator tool call locally.

    Returns
    -------
    (result_dict, sim_result_or_none)
        result_dict : JSON-serializable data to feed back to Claude
        sim_result  : raw SimulationResult(s) for rich rendering, or None
    """
    try:
        if tool_name == "get_simulator_context":
            detail = tool_input.get("detail_level", "full")
            ctx = build_context(detail)
            return ctx.model_dump(), None

        if tool_name == "get_default_scenario":
            return get_default_scenario(), None

        if tool_name == "run_simulation":
            scenario = _build_scenario(tool_input.get("scenario", {}))
            charger = scenario.charger_variants[0]
            result = _run_with_financials(scenario, charger)
            narrative = generate_narrative(result)
            return {
                "result": condense_result(result),
                "narrative": narrative,
            }, result

        if tool_name == "compare_chargers":
            scenario = _build_scenario(tool_input.get("scenario", {}))
            cv_dicts = tool_input.get("charger_variants", [])
            chargers = [ChargerVariant(**cv) for cv in cv_dicts] if cv_dicts else scenario.charger_variants

            results: list[SimulationResult] = []
            for cv in chargers:
                results.append(_run_with_financials(scenario, cv))

            ranking = []
            for r in results:
                ranking.append({
                    "charger": r.summary.charger_variant_name,
                    "cpc_total": round(r.cpc_waterfall.total, 2),
                    "cpc_charger": round(r.cpc_waterfall.charger, 2),
                    "net_cash_flow": round(r.summary.total_net_cash_flow, 2),
                    "break_even_month": r.summary.break_even_month,
                    "npv": round(r.dcf.npv, 2) if r.dcf else None,
                })
            ranking.sort(key=lambda x: x["cpc_total"])

            narrative = generate_comparison_narrative(results)
            return {
                "ranking": ranking,
                "comparison_narrative": narrative,
                "results": [condense_result(r) for r in results],
            }, results

        if tool_name == "run_sensitivity":
            scenario = _build_scenario(tool_input.get("scenario", {}))
            charger = scenario.charger_variants[0]

            sweep_config = None
            if tool_input.get("sweep_params"):
                sweep_config = [
                    (
                        sp.get("name", sp["path"]),
                        sp["path"],
                        sp.get("low_pct", -0.15),
                        sp.get("high_pct", 0.15),
                    )
                    for sp in tool_input["sweep_params"]
                ]

            sens = _run_sensitivity(scenario, charger, sweep_config)
            bars = [
                {
                    "param_name": bar.param_name,
                    "param_path": bar.param_path,
                    "base_value": bar.base_value,
                    "low_value": bar.low_value,
                    "high_value": bar.high_value,
                    "npv_at_low": bar.npv_at_low,
                    "npv_at_high": bar.npv_at_high,
                    "delta_npv": bar.delta_npv,
                }
                for bar in sens.bars
            ]
            return {
                "base_npv": sens.base_npv,
                "tornado_bars": bars,
            }, None

        if tool_name == "optimize_fleet_size":
            scenario = _build_scenario(tool_input.get("scenario", {}))
            charger = scenario.charger_variants[0]

            target = tool_input.get("target", "positive_ncf")
            confidence = tool_input.get("confidence_level", 0.5)
            confidence_pct = confidence * 100 if confidence <= 1.0 else confidence

            pilot = find_minimum_fleet_size(
                scenario=scenario,
                charger=charger,
                target_metric=target,
                target_confidence_pct=confidence_pct,
                min_fleet=tool_input.get("min_fleet", 10),
                max_fleet=tool_input.get("max_fleet", 2000),
                break_even_target_months=tool_input.get("break_even_target_months"),
            )

            sim_result = None
            if pilot.achieved and pilot.recommended_fleet_size > 0:
                scenario.revenue.initial_fleet_size = pilot.recommended_fleet_size
                sim_result = _run_with_financials(scenario, charger)
                narrative = (
                    f"Minimum fleet size to achieve '{target}' at "
                    f"{confidence_pct:.0f}% confidence: "
                    f"{pilot.recommended_fleet_size} vehicles.\n\n"
                    + generate_narrative(sim_result)
                )
            else:
                narrative = (
                    f"Could not find a fleet size between "
                    f"{tool_input.get('min_fleet', 10)} and "
                    f"{tool_input.get('max_fleet', 2000)} that achieves "
                    f"'{target}' at {confidence_pct:.0f}% confidence."
                )

            result_data = {
                "recommended_fleet_size": pilot.recommended_fleet_size,
                "target": target,
                "confidence_level_pct": confidence_pct,
                "achieved": pilot.achieved,
                "narrative": narrative,
            }
            if sim_result:
                result_data["result"] = condense_result(sim_result)
            return result_data, sim_result

        if tool_name == "get_narrative_only":
            scenario = _build_scenario(tool_input.get("scenario", {}))
            charger = scenario.charger_variants[0]
            result = _run_with_financials(scenario, charger)
            narrative = generate_narrative(result)
            return {"narrative": narrative}, None

        return {"error": f"Unknown tool: {tool_name}"}, None

    except Exception as e:
        return {
            "error": True,
            "tool_name": tool_name,
            "message": str(e),
            "type": type(e).__name__,
        }, None
