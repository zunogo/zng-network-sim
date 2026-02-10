"""Pre-built tool/function definitions for LLM integration frameworks.

Generates tool schemas in OpenAI and Anthropic formats, auto-derived
from the Pydantic models. LLMs can use these to call the simulator API.

Usage:
    from zng_simulator.api.tools import get_openai_tools, get_anthropic_tools
"""

from __future__ import annotations

from typing import Any


def get_openai_tools() -> list[dict[str, Any]]:
    """Return tool definitions in OpenAI function-calling format.

    These can be passed directly to ``tools`` parameter in OpenAI chat completions.
    """
    return [
        {
            "type": "function",
            "function": {
                "name": "get_simulator_context",
                "description": (
                    "Get the full context of the ZNG Battery Swap Network Simulator. "
                    "Call this FIRST to understand what the simulator does, what parameters "
                    "are available, and how to interpret results."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "detail_level": {
                            "type": "string",
                            "enum": ["compact", "full"],
                            "description": "compact = schemas only, full = business model + formulas + interpretation guide",
                        },
                    },
                    "required": [],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_default_scenario",
                "description": (
                    "Get the complete default scenario as JSON. "
                    "Use this as a starting point — modify only the fields you want to change."
                ),
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "run_simulation",
                "description": (
                    "Run a battery swap network simulation. Send a partial scenario — "
                    "only include fields you want to change from defaults. "
                    "Returns full financial results + plain-English narrative."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "scenario": {
                            "type": "object",
                            "description": (
                                "Partial scenario overrides. Example: "
                                '{"revenue": {"price_per_swap": 50}, '
                                '"simulation": {"engine": "stochastic", "monte_carlo_runs": 100}}'
                            ),
                        },
                    },
                    "required": [],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "compare_chargers",
                "description": (
                    "Compare multiple charger variants side by side. "
                    "Returns cost-per-cycle breakdown, NPV, break-even, and ranking for each variant."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "scenario": {
                            "type": "object",
                            "description": "Base scenario overrides (without charger_variants)",
                        },
                        "charger_variants": {
                            "type": "array",
                            "items": {"type": "object"},
                            "description": (
                                "List of charger configs to compare. Each needs at minimum: "
                                "name, purchase_cost_per_slot, rated_power_w, mtbf_hours. "
                                "Example: [{'name': 'Budget', 'purchase_cost_per_slot': 8000, "
                                "'rated_power_w': 1000, 'mtbf_hours': 8000}, "
                                "{'name': 'Premium', 'purchase_cost_per_slot': 25000, "
                                "'rated_power_w': 1000, 'mtbf_hours': 40000}]"
                            ),
                        },
                    },
                    "required": ["charger_variants"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "run_sensitivity",
                "description": (
                    "Run sensitivity analysis — vary key parameters and measure NPV impact. "
                    "Returns tornado chart data showing which assumptions matter most."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "scenario": {
                            "type": "object",
                            "description": "Base scenario overrides",
                        },
                        "sweep_params": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "path": {"type": "string", "description": "Parameter path, e.g. 'pack.unit_cost'"},
                                    "low_pct": {"type": "number", "description": "Low end deviation, e.g. -0.15 for -15%"},
                                    "high_pct": {"type": "number", "description": "High end deviation, e.g. 0.15 for +15%"},
                                },
                            },
                            "description": "Optional custom sweep parameters. If omitted, uses default set.",
                        },
                    },
                    "required": [],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "optimize_fleet_size",
                "description": (
                    "Find the minimum fleet size needed to achieve a financial target "
                    "(positive net cash flow or positive NPV) at a specified confidence level."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "scenario": {
                            "type": "object",
                            "description": "Base scenario overrides",
                        },
                        "target": {
                            "type": "string",
                            "enum": ["positive_ncf", "positive_npv"],
                            "description": "Financial target to achieve",
                        },
                        "confidence_level": {
                            "type": "number",
                            "description": "Required confidence (0.5 = median, 0.9 = P90). Default: 0.5",
                        },
                    },
                    "required": [],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_narrative_only",
                "description": (
                    "Run simulation and get ONLY the plain-English narrative interpretation. "
                    "Lighter response — ideal when you want business insights without raw data."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "scenario": {
                            "type": "object",
                            "description": "Partial scenario overrides",
                        },
                    },
                    "required": [],
                },
            },
        },
    ]


def get_anthropic_tools() -> list[dict[str, Any]]:
    """Return tool definitions in Anthropic tool-use format.

    These can be passed directly to ``tools`` parameter in Anthropic messages API.
    """
    openai_tools = get_openai_tools()
    anthropic_tools: list[dict[str, Any]] = []

    for tool in openai_tools:
        func = tool["function"]
        anthropic_tools.append({
            "name": func["name"],
            "description": func["description"],
            "input_schema": func["parameters"],
        })

    return anthropic_tools


def get_system_prompt(base_url: str = "http://localhost:8000") -> str:
    """Generate a system prompt for an LLM that has access to the simulator.

    This prompt tells the LLM what tools are available and how to use them.
    """
    return f"""You are an AI assistant with access to the ZNG Battery Swap Network Simulator.

WHAT THE SIMULATOR DOES:
The ZNG simulator is a digital twin for commercial 2-wheeler battery swapping networks.
It models demand, battery degradation, charger reliability, and produces investor-grade
financial outputs (cost per cycle, NPV, IRR, DSCR, P&L, sensitivity analysis).

YOUR CAPABILITIES:
1. get_simulator_context — Read the full simulator documentation (call this first if unsure)
2. get_default_scenario — Get default input parameters as a starting point
3. run_simulation — Run a simulation with custom parameters
4. compare_chargers — Compare multiple charger variants head-to-head
5. run_sensitivity — Find which assumptions matter most to NPV
6. optimize_fleet_size — Find minimum fleet for financial targets
7. get_narrative_only — Get plain-English business interpretation

API BASE URL: {base_url}

WORKFLOW:
1. Start by understanding the user's question
2. If you need to understand what parameters are available, call get_simulator_context
3. Modify only the parameters relevant to the question (use defaults for everything else)
4. Run the appropriate simulation endpoint
5. Interpret the results and explain the business implications

KEY METRICS TO WATCH:
- Cost per cycle (CPC): the headline unit economics number
- Break-even month: when the project becomes cash-flow positive
- NPV / IRR: overall project value and return
- DSCR: can the project service debt?
- Monte Carlo P10/P50/P90: uncertainty range

IMPORTANT: Always explain results in business terms the user can act on.
Don't just report numbers — explain what they mean and what to do about them.
"""
