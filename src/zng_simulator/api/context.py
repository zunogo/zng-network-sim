"""Context manifest generator — makes the simulator self-describing for LLMs.

Produces structured context at two detail levels:
  - ``compact``: parameter schemas + descriptions (~2K tokens)
  - ``full``:    business model + formulas + interpretation guides (~8K tokens)

An LLM reads ``GET /context?detail=full`` once, then knows exactly
what it can configure, what to run, and how to interpret outputs.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from zng_simulator.config import (
    VehicleConfig, PackSpec, ChargerVariant, StationConfig,
    OpExConfig, RevenueConfig, ChaosConfig, DemandConfig,
    FinanceConfig, SimulationConfig, Scenario,
)


# ═══════════════════════════════════════════════════════════════════════════
# Public response models
# ═══════════════════════════════════════════════════════════════════════════

class ParameterInfo(BaseModel):
    """One configurable parameter, machine-readable."""
    name: str
    type: str
    default: Any
    description: str
    constraints: dict[str, Any] = Field(default_factory=dict)


class SectionSchema(BaseModel):
    """Schema for one configuration section (e.g. vehicle, pack)."""
    section: str
    description: str
    parameters: list[ParameterInfo]


class OutputFieldInfo(BaseModel):
    """One output field, machine-readable."""
    name: str
    type: str
    description: str
    unit: str = ""


class EndpointInfo(BaseModel):
    """Description of one API endpoint."""
    method: str
    path: str
    description: str
    request_body: str = ""
    response: str = ""


class SimulatorContext(BaseModel):
    """Full self-describing context for LLM consumption."""
    simulator_name: str
    version: str
    description: str
    business_model: str
    key_formulas: list[dict[str, str]]
    input_sections: list[SectionSchema]
    key_outputs: list[OutputFieldInfo]
    endpoints: list[EndpointInfo]
    interpretation_guide: str
    example_queries: list[dict[str, str]]


# ═══════════════════════════════════════════════════════════════════════════
# Schema extraction from Pydantic models
# ═══════════════════════════════════════════════════════════════════════════

def _extract_params(model_cls: type[BaseModel]) -> list[ParameterInfo]:
    """Extract parameter info from a Pydantic model class."""
    params: list[ParameterInfo] = []
    for name, field_info in model_cls.model_fields.items():
        constraints: dict[str, Any] = {}
        for attr in ("ge", "gt", "le", "lt"):
            meta_val = _get_field_metadata(field_info, attr)
            if meta_val is not None:
                constraints[attr] = meta_val

        default = field_info.default
        if default is not None and not callable(default):
            default_val = default
        else:
            default_val = None

        type_str = str(field_info.annotation) if field_info.annotation else "Any"
        # Clean up type string
        type_str = type_str.replace("typing.", "").replace("<class '", "").replace("'>", "")

        params.append(ParameterInfo(
            name=name,
            type=type_str,
            default=default_val,
            description=field_info.description or "",
            constraints=constraints,
        ))
    return params


def _get_field_metadata(field_info: Any, attr: str) -> Any:
    """Extract constraint metadata from Pydantic field info."""
    # Check direct metadata
    if hasattr(field_info, 'metadata'):
        for m in field_info.metadata:
            if hasattr(m, attr):
                return getattr(m, attr)
    return None


# ═══════════════════════════════════════════════════════════════════════════
# Context builders
# ═══════════════════════════════════════════════════════════════════════════

_BUSINESS_MODEL = """
ZNG Battery Swap Network Simulator — Digital Twin & Financial Model

WHAT IT DOES:
Simulates the full lifecycle economics of a commercial 2-wheeler battery swapping
network. Drivers arrive at stations, swap depleted battery packs for charged ones,
and drive away. The simulator models:
  - Demand: how many swap visits per day (Poisson, Gamma, or Bimodal distribution)
  - Battery degradation: SOH decays with cycles and calendar time, triggering replacements
  - Charger reliability: chargers fail stochastically (exponential or Weibull MTBF)
  - Revenue: per-swap pricing × fleet size × utilization
  - Cost per cycle: 9-component waterfall (battery, charger, electricity, rent, etc.)
  - Financial statements: P&L, cash flow, DCF, NPV, IRR, DSCR

THE BUSINESS:
  - Revenue = price_per_swap × packs_per_vehicle × swap_visits_per_day × fleet_size × 30
  - Cost = CapEx (stations + chargers + packs) + OpEx (electricity + rent + maintenance + labor + insurance + logistics + overhead)
  - Unit economics metric = "fully-loaded cost per cycle" — what one charge-discharge cycle truly costs

KEY DECISIONS THE SIMULATOR HELPS MAKE:
  1. Charger selection: which charger variant minimizes lifetime TCO (including MTBF economics)?
  2. Pilot sizing: what is the minimum fleet size to reach positive operating cash flow?
  3. Bankability: can this project service debt? What DSCR does a lender see?
  4. Sensitivity: which input assumptions matter most to NPV?
"""

_INTERPRETATION_GUIDE = """
HOW TO INTERPRET RESULTS:

1. COST PER CYCLE (CPC):
   The headline number. Lower is better. Decompose via the waterfall to see where
   money goes. Battery and charger components are the main levers.
   - CPC < price_per_swap → unit economics work
   - CPC > price_per_swap → loss per swap

2. BREAK-EVEN MONTH:
   The month when cumulative cash flow turns positive. Earlier is better.
   If None, the project never breaks even under these assumptions.

3. NPV / IRR:
   NPV > 0 means the project creates value above the discount rate.
   IRR is the discount rate that makes NPV = 0. Higher IRR = better return.

4. DSCR:
   Debt Service Coverage Ratio = NOI / debt payment.
   DSCR > 1.2 is typically required by lenders. Below 1.0 = cannot service debt.

5. MONTE CARLO P10/P50/P90:
   P10 = pessimistic (only 10% of outcomes are worse).
   P50 = median (50/50).
   P90 = optimistic (90% of outcomes are worse).
   The P10-P90 spread shows how much uncertainty exists.

6. CHARGER COMPARISON:
   Run with multiple charger variants. Compare by:
   - NPV of network using each charger (higher = better)
   - CPC contribution (lower = cheaper per cycle)
   - Break-even month (earlier = better)

COMMON ANALYSIS PATTERNS:
  - "What if pack cost drops 20%?" → adjust pack.unit_cost, re-run, compare NPV
  - "What if MTBF is worse than spec?" → lower charger.mtbf_hours, see CPC impact
  - "What is the minimum fleet for break-even?" → use /simulate/optimize endpoint
  - "Compare chargers" → set charger_variants list, compare results side by side
  - "Stress test" → use sensitivity endpoint with multiple parameter sweeps
"""

_KEY_FORMULAS = [
    {
        "name": "Swaps per vehicle per day",
        "formula": "(avg_daily_km × energy_consumption_wh_per_km) / (pack_capacity_kwh × 1000 × (1 - range_anxiety_buffer_pct))",
        "meaning": "How often each vehicle needs a battery swap — drives all downstream demand",
    },
    {
        "name": "Cost per cycle — Battery component",
        "formula": "(pack_unit_cost - salvage_value) / pack_lifetime_cycles + failure_cost_per_cycle",
        "meaning": "Amortized battery cost per charge-discharge cycle, including degradation replacement and random failures",
    },
    {
        "name": "Cost per cycle — Charger component",
        "formula": "charger_fleet_TCO / total_cycles_served_over_horizon",
        "meaning": "Charger TCO (purchase + repairs + replacements + downtime revenue loss + spares) per cycle",
    },
    {
        "name": "Net Present Value",
        "formula": "Σ (net_cash_flow_t / (1 + r)^t) + terminal_value / (1 + r)^T",
        "meaning": "Present value of all future cash flows minus initial investment. Positive = value-creating.",
    },
    {
        "name": "DSCR",
        "formula": "NOI_monthly / debt_service_monthly",
        "meaning": "Debt Service Coverage Ratio. Must be > 1.0 to service debt, > 1.2 for bank comfort.",
    },
    {
        "name": "Charger MTBF economics",
        "formula": "TCO = CapEx + PV(repairs) + PV(replacements) + PV(lost_revenue) + PV(spares) - PV(salvage)",
        "meaning": "A cheap charger with low MTBF can cost MORE over 5 years than an expensive reliable one.",
    },
]


_EXAMPLE_QUERIES = [
    {
        "query": "Run a base-case simulation with default parameters",
        "action": "POST /simulate with empty body (uses all defaults)",
    },
    {
        "query": "What happens if we use LFP chemistry instead of NMC?",
        "action": "POST /simulate with pack.chemistry='LFP', pack.cycle_degradation_rate_pct=0.02, pack.unit_cost=12000",
    },
    {
        "query": "Compare a budget charger vs premium charger",
        "action": "POST /simulate/compare with two charger variants differing in purchase_cost and mtbf_hours",
    },
    {
        "query": "What is the minimum fleet for positive cash flow at 90% confidence?",
        "action": "POST /simulate/optimize with target='positive_ncf' and confidence=0.9",
    },
    {
        "query": "Which parameters matter most to NPV?",
        "action": "POST /simulate/sensitivity to get a tornado chart ranking parameters by NPV impact",
    },
    {
        "query": "Stress test: what if MTBF is 50% worse and electricity costs rise 20%?",
        "action": "POST /simulate with charger.mtbf_hours halved and opex.electricity_tariff_per_kwh increased by 20%",
    },
    {
        "query": "Show me the full P&L and cash flow statement",
        "action": "POST /simulate then read result.financial_statements.pnl and result.financial_statements.cash_flow",
    },
]


_KEY_OUTPUTS = [
    OutputFieldInfo(name="summary.avg_cost_per_cycle", type="float", description="Fully-loaded cost per charge-discharge cycle (₹)", unit="₹/cycle"),
    OutputFieldInfo(name="summary.break_even_month", type="int|None", description="Month when cumulative cash flow turns positive", unit="month"),
    OutputFieldInfo(name="summary.total_revenue", type="float", description="Total revenue over the simulation horizon", unit="₹"),
    OutputFieldInfo(name="summary.total_net_cash_flow", type="float", description="Net cash flow over the simulation horizon", unit="₹"),
    OutputFieldInfo(name="dcf.npv", type="float", description="Net Present Value of all cash flows", unit="₹"),
    OutputFieldInfo(name="dcf.irr", type="float|None", description="Internal Rate of Return (annualized)", unit="%"),
    OutputFieldInfo(name="dcf.discounted_payback_month", type="int|None", description="Month when discounted cumulative CF ≥ 0", unit="month"),
    OutputFieldInfo(name="dscr.avg_dscr", type="float", description="Average Debt Service Coverage Ratio", unit="ratio"),
    OutputFieldInfo(name="dscr.min_dscr", type="float", description="Minimum DSCR in any month", unit="ratio"),
    OutputFieldInfo(name="dscr.breach_months", type="list[int]", description="Months where DSCR < covenant threshold", unit="months"),
    OutputFieldInfo(name="cpc_waterfall.battery", type="float", description="Battery cost per cycle", unit="₹/cycle"),
    OutputFieldInfo(name="cpc_waterfall.charger", type="float", description="Charger cost per cycle", unit="₹/cycle"),
    OutputFieldInfo(name="cpc_waterfall.electricity", type="float", description="Electricity cost per cycle", unit="₹/cycle"),
    OutputFieldInfo(name="cpc_waterfall.total", type="float", description="Total cost per cycle (all 9 components)", unit="₹/cycle"),
    OutputFieldInfo(name="monte_carlo.ncf_p10", type="float", description="10th percentile net cash flow (pessimistic)", unit="₹"),
    OutputFieldInfo(name="monte_carlo.ncf_p50", type="float", description="Median net cash flow", unit="₹"),
    OutputFieldInfo(name="monte_carlo.ncf_p90", type="float", description="90th percentile net cash flow (optimistic)", unit="₹"),
]


_ENDPOINTS = [
    EndpointInfo(
        method="GET", path="/context",
        description="Returns this self-describing context. Use detail_level='compact' for schemas only, 'full' for business model + formulas + interpretation guide.",
        response="SimulatorContext",
    ),
    EndpointInfo(
        method="GET", path="/schema",
        description="Returns the full JSON schema for Scenario (all input parameters with types, defaults, constraints).",
        response="JSON Schema object",
    ),
    EndpointInfo(
        method="GET", path="/scenario/defaults",
        description="Returns a complete default Scenario as JSON. Useful as a starting point for modifications.",
        response="Scenario JSON",
    ),
    EndpointInfo(
        method="POST", path="/simulate",
        description="Run a full simulation. Send a Scenario JSON (or partial — missing fields use defaults). Returns SimulationResult with financials.",
        request_body="Scenario (partial or full)",
        response="SimulationResult with DCF, DSCR, P&L attached",
    ),
    EndpointInfo(
        method="POST", path="/simulate/compare",
        description="Run simulation for multiple charger variants and return side-by-side comparison. Send Scenario with charger_variants list.",
        request_body="Scenario with multiple charger_variants",
        response="List of SimulationResult (one per charger), plus comparison summary",
    ),
    EndpointInfo(
        method="POST", path="/simulate/sensitivity",
        description="Run automated parameter sweeps and return NPV impact ranking (tornado chart data).",
        request_body="Scenario + optional sweep_params override",
        response="List of TornadoBar sorted by NPV impact",
    ),
    EndpointInfo(
        method="POST", path="/simulate/optimize",
        description="Find minimum fleet size for a financial target (e.g., positive NCF) at a confidence level.",
        request_body="Scenario + target + confidence_level",
        response="Optimal fleet size + supporting simulation result",
    ),
    EndpointInfo(
        method="POST", path="/simulate/narrative",
        description="Run simulation and return plain-English interpretation alongside raw results.",
        request_body="Scenario (partial or full)",
        response="SimulationResult + narrative text",
    ),
]


_INPUT_SECTIONS = [
    ("vehicle", VehicleConfig, "Vehicle configuration — defines how demand translates into swap events"),
    ("pack", PackSpec, "Battery pack specification — degradation, costs, failure model"),
    ("charger_variants", ChargerVariant, "Charger variant (can have multiple) — MTBF, costs, failure distribution"),
    ("station", StationConfig, "Station infrastructure — docks, CapEx, operating hours"),
    ("opex", OpExConfig, "Operating expenses — electricity, rent, maintenance, labor, insurance"),
    ("revenue", RevenueConfig, "Revenue model — pricing, fleet size, growth"),
    ("chaos", ChaosConfig, "Risk factors — sabotage, aggressiveness, thermal throttling"),
    ("demand", DemandConfig, "Demand model — distribution type, volatility, seasonality"),
    ("finance", FinanceConfig, "Financial assumptions — debt, depreciation, tax, terminal value"),
    ("simulation", SimulationConfig, "Simulation settings — horizon, engine type, Monte Carlo runs"),
]


# ═══════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════

def build_context(detail_level: Literal["compact", "full"] = "full") -> SimulatorContext:
    """Build the self-describing context manifest.

    Parameters
    ----------
    detail_level : "compact" | "full"
        compact — parameter schemas + descriptions only
        full    — includes business model, formulas, interpretation guide
    """
    sections: list[SectionSchema] = []
    for section_name, model_cls, desc in _INPUT_SECTIONS:
        sections.append(SectionSchema(
            section=section_name,
            description=desc,
            parameters=_extract_params(model_cls),
        ))

    return SimulatorContext(
        simulator_name="ZNG Battery Swap Network Simulator",
        version="2.0",
        description=(
            "Digital twin and financial simulator for commercial 2-wheeler battery swapping networks. "
            "Produces investor-grade outputs: unit economics (cost per cycle), charger TCO comparison, "
            "DCF/NPV/IRR, DSCR, P&L, sensitivity analysis, and Monte Carlo confidence intervals."
        ),
        business_model=_BUSINESS_MODEL.strip() if detail_level == "full" else "",
        key_formulas=_KEY_FORMULAS if detail_level == "full" else [],
        input_sections=sections,
        key_outputs=_KEY_OUTPUTS,
        endpoints=_ENDPOINTS,
        interpretation_guide=_INTERPRETATION_GUIDE.strip() if detail_level == "full" else "",
        example_queries=_EXAMPLE_QUERIES if detail_level == "full" else [],
    )


def get_scenario_schema() -> dict:
    """Return the full JSON Schema for Scenario."""
    return Scenario.model_json_schema()


def get_default_scenario() -> dict:
    """Return default Scenario as a JSON-serializable dict."""
    return Scenario().model_dump()
