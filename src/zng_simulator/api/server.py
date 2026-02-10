"""FastAPI server — LLM-accessible API for the ZNG simulator.

Run with:
    uvicorn zng_simulator.api.server:app --reload --port 8000

Or:
    python -m zng_simulator.api.server

Endpoints:
    GET  /context              — self-describing manifest (business model + schemas)
    GET  /schema               — full JSON Schema for Scenario inputs
    GET  /scenario/defaults    — complete default scenario as JSON
    POST /simulate             — run a full simulation (partial or full Scenario)
    POST /simulate/compare     — compare multiple charger variants
    POST /simulate/sensitivity — parameter sweep → tornado data
    POST /simulate/optimize    — find minimum fleet for financial target
    POST /simulate/narrative   — run + plain-English interpretation
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from zng_simulator.config.scenario import Scenario
from zng_simulator.config.charger import ChargerVariant
from zng_simulator.engine.orchestrator import run_engine
from zng_simulator.finance.dcf import build_dcf_table
from zng_simulator.finance.dscr import build_debt_schedule, compute_dscr
from zng_simulator.finance.statements import build_financial_statements
from zng_simulator.finance.sensitivity import run_sensitivity
from zng_simulator.engine.optimizer import find_minimum_fleet_size
from zng_simulator.models.results import SimulationResult
from zng_simulator.api.context import build_context, get_scenario_schema, get_default_scenario
from zng_simulator.api.narrative import generate_narrative, generate_comparison_narrative
from zng_simulator.api.tools import get_openai_tools, get_anthropic_tools, get_system_prompt


# ═══════════════════════════════════════════════════════════════════════════
# App setup
# ═══════════════════════════════════════════════════════════════════════════

app = FastAPI(
    title="ZNG Battery Swap Network Simulator API",
    version="2.0",
    description=(
        "LLM-accessible API for the ZNG Battery Swap Network Digital Twin & "
        "Financial Simulator. Configure scenarios, run simulations, compare "
        "charger variants, and get plain-English interpretations of results. "
        "Start by calling GET /context to understand the full simulator."
    ),
)

# Allow all origins for LLM tool access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ═══════════════════════════════════════════════════════════════════════════
# Request / response models
# ═══════════════════════════════════════════════════════════════════════════

class SimulateRequest(BaseModel):
    """Request body for /simulate. All fields optional — defaults used for missing."""
    scenario: dict[str, Any] = Field(
        default_factory=dict,
        description="Partial or full Scenario JSON. Missing fields use defaults. "
                    "Example: {'revenue': {'price_per_swap': 50}, 'simulation': {'engine': 'stochastic'}}",
    )


class CompareRequest(BaseModel):
    """Request body for /simulate/compare."""
    scenario: dict[str, Any] = Field(
        default_factory=dict,
        description="Base scenario (without charger_variants — those go in the list below)",
    )
    charger_variants: list[dict[str, Any]] = Field(
        default_factory=list,
        description="List of charger variant configs to compare. "
                    "Example: [{'name': 'Budget', 'mtbf_hours': 8000}, {'name': 'Premium', 'mtbf_hours': 40000}]",
    )


class SensitivityRequest(BaseModel):
    """Request body for /simulate/sensitivity."""
    scenario: dict[str, Any] = Field(default_factory=dict)
    sweep_params: list[dict[str, Any]] | None = Field(
        default=None,
        description="Optional override of sweep parameters. "
                    "Default sweeps: pack.unit_cost ±15%, charger.mtbf_hours ±20%, etc. "
                    "Format: [{'name': 'My param', 'path': 'pack.unit_cost', 'low_pct': -0.15, 'high_pct': 0.15}]",
    )


class OptimizeRequest(BaseModel):
    """Request body for /simulate/optimize."""
    scenario: dict[str, Any] = Field(default_factory=dict)
    target: Literal["positive_ncf", "positive_npv", "break_even_within"] = Field(
        default="positive_ncf",
        description="Financial target: 'positive_ncf' (net cash flow > 0), "
                    "'positive_npv' (NPV > 0), or 'break_even_within' (break-even ≤ N months)",
    )
    confidence_level_pct: float = Field(
        default=50.0,
        ge=1.0,
        le=99.0,
        description="Required confidence level in percent. "
                    "50 = median (P50), 90 = P10 must meet target (90%% of runs succeed).",
    )
    min_fleet: int = Field(default=10, ge=1, description="Search range: minimum fleet size")
    max_fleet: int = Field(default=2000, ge=10, description="Search range: maximum fleet size")
    break_even_target_months: int | None = Field(
        default=None,
        description="Required for target='break_even_within'. Target month for break-even.",
    )


class SimulateResponse(BaseModel):
    """Response from /simulate."""
    result: dict[str, Any]
    narrative: str = ""


class CompareResponse(BaseModel):
    """Response from /simulate/compare."""
    results: list[dict[str, Any]]
    comparison_narrative: str
    ranking: list[dict[str, Any]]


class OptimizeResponse(BaseModel):
    """Response from /simulate/optimize."""
    recommended_fleet_size: int
    target: str
    confidence_level_pct: float
    achieved: bool
    pilot_result: dict[str, Any]
    narrative: str = ""


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════

def _build_scenario(overrides: dict[str, Any]) -> Scenario:
    """Build a Scenario from partial overrides merged onto defaults."""
    defaults = get_default_scenario()
    _deep_merge(defaults, overrides)
    return Scenario(**defaults)


def _deep_merge(base: dict, overrides: dict) -> dict:
    """Recursively merge overrides into base dict."""
    for key, val in overrides.items():
        if key in base and isinstance(base[key], dict) and isinstance(val, dict):
            _deep_merge(base[key], val)
        else:
            base[key] = val
    return base


def _run_with_financials(scenario: Scenario, charger: ChargerVariant) -> SimulationResult:
    """Run engine + attach financial overlays (DCF, DSCR, statements)."""
    result = run_engine(scenario, charger)

    fin = scenario.finance
    sim = scenario.simulation
    total_capex = result.summary.total_capex
    salvage = result.derived.total_packs * scenario.pack.second_life_salvage_value

    # DCF
    try:
        result.dcf = build_dcf_table(
            result.months, result.summary, fin,
            sim.discount_rate_annual, salvage,
        )
    except Exception:
        pass

    # Debt schedule + DSCR
    debt_sched = None
    try:
        debt_sched = build_debt_schedule(total_capex, fin, sim.horizon_months)
        result.debt_schedule = debt_sched
        result.dscr = compute_dscr(result.months, debt_sched, fin)
    except Exception:
        pass

    # Financial statements
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


# ═══════════════════════════════════════════════════════════════════════════
# Endpoints
# ═══════════════════════════════════════════════════════════════════════════

@app.get("/health")
def health_check():
    """Health check for deployment platforms (Render, Railway, etc.)."""
    return {"status": "ok"}


@app.get("/")
def root():
    """API root — returns a welcome message and pointer to /context."""
    return {
        "name": "ZNG Battery Swap Network Simulator API",
        "version": "2.0",
        "start_here": "GET /context?detail_level=full",
        "docs": "GET /docs (interactive Swagger UI)",
        "description": "LLM-accessible API for battery swap network simulation and financial modeling.",
    }


@app.get("/context")
def get_context(
    detail_level: Literal["compact", "full"] = Query(
        default="full",
        description="'compact' for schemas only, 'full' for business model + formulas + guide",
    ),
):
    """Self-describing context manifest for LLM consumption.

    Call this FIRST to understand what the simulator does, what parameters
    are available, what outputs are produced, and how to interpret results.
    """
    return build_context(detail_level)


@app.get("/schema")
def get_schema():
    """Full JSON Schema for Scenario — all input parameters with types, defaults, constraints."""
    return get_scenario_schema()


@app.get("/scenario/defaults")
def get_defaults():
    """Complete default Scenario as JSON. Use as a starting point for modifications."""
    return get_default_scenario()


@app.post("/simulate", response_model=SimulateResponse)
def simulate(req: SimulateRequest):
    """Run a full simulation with financial overlays.

    Send a partial Scenario (only the fields you want to change).
    Missing fields use defaults. Returns full SimulationResult + narrative.

    Example minimal request:
    ```json
    {"scenario": {"revenue": {"price_per_swap": 50}, "simulation": {"engine": "stochastic", "monte_carlo_runs": 100}}}
    ```
    """
    scenario = _build_scenario(req.scenario)
    charger = scenario.charger_variants[0]
    result = _run_with_financials(scenario, charger)
    narrative = generate_narrative(result)
    return SimulateResponse(
        result=result.model_dump(),
        narrative=narrative,
    )


@app.post("/simulate/compare", response_model=CompareResponse)
def simulate_compare(req: CompareRequest):
    """Compare multiple charger variants side by side.

    Send a base scenario + list of charger variant configs.
    Returns one SimulationResult per variant + comparison narrative + ranking.
    """
    scenario = _build_scenario(req.scenario)

    if req.charger_variants:
        chargers = [ChargerVariant(**cv) for cv in req.charger_variants]
    else:
        chargers = scenario.charger_variants

    results: list[SimulationResult] = []
    for cv in chargers:
        result = _run_with_financials(scenario, cv)
        results.append(result)

    ranking: list[dict[str, Any]] = []
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

    return CompareResponse(
        results=[r.model_dump() for r in results],
        comparison_narrative=narrative,
        ranking=ranking,
    )


@app.post("/simulate/sensitivity")
def simulate_sensitivity(req: SensitivityRequest):
    """Run automated parameter sweeps and return NPV impact ranking.

    Returns tornado chart data: for each parameter, the NPV at low and high
    values, sorted by absolute impact. This shows which assumptions matter most.
    """
    scenario = _build_scenario(req.scenario)
    charger = scenario.charger_variants[0]

    sweep_config = None
    if req.sweep_params:
        sweep_config = [
            (sp.get("name", sp["path"]), sp["path"], sp.get("low_pct", -0.15), sp.get("high_pct", 0.15))
            for sp in req.sweep_params
        ]

    sensitivity_result = run_sensitivity(scenario, charger, sweep_config)

    return {
        "base_npv": sensitivity_result.base_npv,
        "tornado_bars": [
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
            for bar in sensitivity_result.bars
        ],
        "interpretation": (
            "Sorted by absolute NPV impact (largest first). "
            "Parameters at the top of the list are the ones that matter most. "
            "A large spread between low and high NPV means the project is sensitive to that assumption."
        ),
    }


@app.post("/simulate/optimize", response_model=OptimizeResponse)
def simulate_optimize(req: OptimizeRequest):
    """Find the minimum fleet size to achieve a financial target.

    Uses binary search across fleet sizes, running the engine at each point,
    to find the smallest fleet where the target is met at the specified confidence.
    """
    scenario = _build_scenario(req.scenario)
    charger = scenario.charger_variants[0]

    pilot_result = find_minimum_fleet_size(
        scenario=scenario,
        charger=charger,
        target_metric=req.target,
        target_confidence_pct=req.confidence_level_pct,
        min_fleet=req.min_fleet,
        max_fleet=req.max_fleet,
        break_even_target_months=req.break_even_target_months,
    )

    fleet = pilot_result.recommended_fleet_size
    if pilot_result.achieved and fleet > 0:
        scenario.revenue.initial_fleet_size = fleet
        result = _run_with_financials(scenario, charger)
        narrative = (
            f"Minimum fleet size to achieve '{req.target}' at {req.confidence_level_pct:.0f}% "
            f"confidence: {fleet} vehicles.\n\n"
            + generate_narrative(result)
        )
    else:
        narrative = (
            f"Could not find a fleet size between {req.min_fleet} and {req.max_fleet} "
            f"that achieves '{req.target}' at {req.confidence_level_pct:.0f}% confidence. "
            f"Consider widening the search range or relaxing the confidence level."
        )

    return OptimizeResponse(
        recommended_fleet_size=pilot_result.recommended_fleet_size,
        target=req.target,
        confidence_level_pct=req.confidence_level_pct,
        achieved=pilot_result.achieved,
        pilot_result=pilot_result.model_dump(),
        narrative=narrative,
    )


@app.get("/tools/openai")
def get_openai_tool_definitions():
    """Pre-built tool/function definitions in OpenAI function-calling format.

    Copy-paste these into your OpenAI ``tools`` parameter to give an LLM
    the ability to call this simulator via function calling.
    """
    return {
        "tools": get_openai_tools(),
        "system_prompt": get_system_prompt(),
        "usage": (
            "1. Add these tools to your OpenAI chat completion request\n"
            "2. Use the system_prompt as your system message\n"
            "3. The LLM will call these functions as needed\n"
            "4. Map function calls to the corresponding API endpoints"
        ),
    }


@app.get("/tools/anthropic")
def get_anthropic_tool_definitions():
    """Pre-built tool definitions in Anthropic tool-use format.

    Copy-paste these into your Anthropic ``tools`` parameter.
    """
    return {
        "tools": get_anthropic_tools(),
        "system_prompt": get_system_prompt(),
        "usage": (
            "1. Add these tools to your Anthropic messages API request\n"
            "2. Use the system_prompt as your system message\n"
            "3. The LLM will use tool_use blocks to call these functions\n"
            "4. Map tool calls to the corresponding API endpoints"
        ),
    }


@app.post("/simulate/narrative")
def simulate_with_narrative(req: SimulateRequest):
    """Run simulation and return ONLY the plain-English narrative.

    Same as /simulate but returns just the narrative text — ideal for
    LLMs that want to reason about the business model without parsing raw data.
    """
    scenario = _build_scenario(req.scenario)
    charger = scenario.charger_variants[0]
    result = _run_with_financials(scenario, charger)
    return {
        "narrative": generate_narrative(result),
        "headline_metrics": {
            "cost_per_cycle": round(result.cpc_waterfall.total, 2),
            "break_even_month": result.summary.break_even_month,
            "total_net_cash_flow": round(result.summary.total_net_cash_flow, 2),
            "npv": round(result.dcf.npv, 2) if result.dcf else None,
            "irr": round(result.dcf.irr, 4) if result.dcf and result.dcf.irr else None,
            "avg_dscr": round(result.dscr.avg_dscr, 2) if result.dscr else None,
        },
    }


# ═══════════════════════════════════════════════════════════════════════════
# CLI entry point
# ═══════════════════════════════════════════════════════════════════════════

def main():
    """Run the API server."""
    import uvicorn
    uvicorn.run(
        "zng_simulator.api.server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )


if __name__ == "__main__":
    main()
