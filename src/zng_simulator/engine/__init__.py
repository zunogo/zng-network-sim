"""Engine — Phase 1 deterministic + Phase 2 stochastic computation logic."""

from zng_simulator.engine.derived import compute_derived_params
from zng_simulator.engine.charger_tco import compute_charger_tco
from zng_simulator.engine.pack_tco import compute_pack_tco
from zng_simulator.engine.cost_per_cycle import compute_cpc_waterfall
from zng_simulator.engine.cashflow import run_simulation
from zng_simulator.engine.demand import generate_daily_demand, generate_monthly_demand
from zng_simulator.engine.degradation import DegradationTracker, DegradationStepResult
from zng_simulator.engine.charger_reliability import ChargerReliabilityTracker, ChargerReliabilityStepResult
from zng_simulator.engine.orchestrator import run_engine

__all__ = [
    "compute_derived_params",
    "compute_charger_tco",
    "compute_pack_tco",
    "compute_cpc_waterfall",
    "run_simulation",
    # Phase 2
    "run_engine",
    "generate_daily_demand",
    "generate_monthly_demand",
    "DegradationTracker",
    "DegradationStepResult",
    "ChargerReliabilityTracker",
    "ChargerReliabilityStepResult",
]
