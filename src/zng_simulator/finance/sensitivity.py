"""Sensitivity / tornado analysis — Phase 3 (§8.2).

Automated parameter sweeps: vary one input at a time, measure output delta.
Produces tornado chart data sorted by impact on NPV.

Default sweep set:
  - pack.unit_cost ± 15%
  - charger.mtbf_hours ± 20%
  - opex.electricity_tariff_per_kwh ± 10%
  - revenue.price_per_swap ± 10%
  - pack.cycle_degradation_rate_pct ± 20%
  - revenue.initial_fleet_size ± 25%
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field

from zng_simulator.config.scenario import Scenario
from zng_simulator.config.charger import ChargerVariant
from zng_simulator.engine.orchestrator import run_engine
from zng_simulator.finance.dcf import build_dcf_table


@dataclass(frozen=True)
class TornadoBar:
    """One bar in the tornado chart."""

    param_name: str
    """Human-readable parameter name."""

    param_path: str
    """Dot-path into Scenario (e.g. 'pack.unit_cost')."""

    base_value: float
    """Value in the base scenario."""

    low_value: float
    """Swept low value."""

    high_value: float
    """Swept high value."""

    npv_at_low: float
    """NPV when param = low_value."""

    npv_at_high: float
    """NPV when param = high_value."""

    delta_npv: float
    """abs(npv_at_high − npv_at_low) — total swing width."""


@dataclass
class SensitivityResult:
    """Complete sensitivity analysis output."""

    base_npv: float
    """NPV of the base scenario."""

    bars: list[TornadoBar] = field(default_factory=list)
    """Tornado bars sorted by delta_npv (descending)."""


# Default sweep parameters
DEFAULT_SWEEPS: list[tuple[str, str, float, float]] = [
    ("Pack unit cost", "pack.unit_cost", -0.15, 0.15),
    ("Charger MTBF", "charger.mtbf_hours", -0.20, 0.20),
    ("Electricity tariff", "opex.electricity_tariff_per_kwh", -0.10, 0.10),
    ("Swap price", "revenue.price_per_swap", -0.10, 0.10),
    ("Degradation rate β", "pack.cycle_degradation_rate_pct", -0.20, 0.20),
    ("Initial fleet size", "revenue.initial_fleet_size", -0.25, 0.25),
]


def _get_nested_attr(obj: object, path: str) -> float:
    """Get a nested attribute via dot-path string."""
    parts = path.split(".")
    current = obj
    for part in parts:
        current = getattr(current, part)
    return float(current)


def _set_nested_attr(obj: object, path: str, value: float) -> None:
    """Set a nested attribute via dot-path string.

    For Pydantic models, we use model_copy to create modified versions.
    If the target field is typed as ``int``, the value is rounded first
    to avoid Pydantic validation errors from fractional sweeps.
    """
    parts = path.split(".")
    current = obj
    for part in parts[:-1]:
        current = getattr(current, part)

    # If target field expects int, round the swept value
    from pydantic import BaseModel as _BM
    if isinstance(current, _BM):
        field_info = type(current).model_fields.get(parts[-1])
        if field_info and field_info.annotation is int:
            value = round(value)

    setattr(current, parts[-1], value)


def _run_npv(scenario: Scenario, charger: ChargerVariant) -> float:
    """Run simulation and compute NPV for a given scenario + charger."""
    result = run_engine(scenario, charger)
    salvage = (result.derived.total_packs * scenario.pack.second_life_salvage_value)
    dcf = build_dcf_table(
        result.months, result.summary, scenario.finance,
        scenario.simulation.discount_rate_annual, salvage,
    )
    return dcf.npv


def run_sensitivity(
    scenario: Scenario,
    charger: ChargerVariant,
    sweeps: list[tuple[str, str, float, float]] | None = None,
) -> SensitivityResult:
    """Run sensitivity analysis for one charger variant.

    Parameters
    ----------
    scenario : Scenario
        Base scenario.
    charger : ChargerVariant
        Charger to evaluate.
    sweeps : list[tuple[name, path, low_pct, high_pct]] | None
        Parameter sweeps. None = use DEFAULT_SWEEPS.

    Returns
    -------
    SensitivityResult
        Tornado bars sorted by NPV impact.
    """
    if sweeps is None:
        sweeps = DEFAULT_SWEEPS

    # Force static engine for sensitivity (faster)
    base_scenario = deepcopy(scenario)
    base_scenario.simulation.engine = "static"
    base_scenario.simulation.monte_carlo_runs = 1

    base_npv = _run_npv(base_scenario, charger)

    bars: list[TornadoBar] = []

    for name, path, low_pct, high_pct in sweeps:
        # Handle charger-specific paths
        if path.startswith("charger."):
            attr_name = path.split(".", 1)[1]
            base_val = float(getattr(charger, attr_name))
        else:
            try:
                base_val = _get_nested_attr(base_scenario, path)
            except AttributeError:
                continue

        low_val = base_val * (1 + low_pct)
        high_val = base_val * (1 + high_pct)

        # Run at low value
        low_scenario = deepcopy(base_scenario)
        low_charger = deepcopy(charger)
        if path.startswith("charger."):
            setattr(low_charger, path.split(".", 1)[1], low_val)
        else:
            _set_nested_attr(low_scenario, path, low_val)
        npv_low = _run_npv(low_scenario, low_charger)

        # Run at high value
        high_scenario = deepcopy(base_scenario)
        high_charger = deepcopy(charger)
        if path.startswith("charger."):
            setattr(high_charger, path.split(".", 1)[1], high_val)
        else:
            _set_nested_attr(high_scenario, path, high_val)
        npv_high = _run_npv(high_scenario, high_charger)

        bars.append(TornadoBar(
            param_name=name,
            param_path=path,
            base_value=round(base_val, 4),
            low_value=round(low_val, 4),
            high_value=round(high_val, 4),
            npv_at_low=round(npv_low, 2),
            npv_at_high=round(npv_high, 2),
            delta_npv=round(abs(npv_high - npv_low), 2),
        ))

    # Sort by impact (largest swing first)
    bars.sort(key=lambda b: b.delta_npv, reverse=True)

    return SensitivityResult(base_npv=round(base_npv, 2), bars=bars)
