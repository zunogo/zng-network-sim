"""Pilot sizing optimizer — Phase 4 (§9).

Answers: "What is the minimum fleet size to achieve positive operating
cash flow (or positive NPV, or break-even within N months) at a
specified confidence level?"

Search strategy (binary search over fleet sizes):
  1. Define search bounds: [min_fleet, max_fleet]
  2. For each candidate fleet_size, run the engine (static or stochastic)
  3. Extract the target metric (NCF > 0, NPV > 0, break-even ≤ target)
  4. Binary-search for the minimum fleet_size that passes the target
  5. Return PilotSizingResult with the recommendation

For stochastic engines, the confidence level determines which percentile
to test against.  E.g. confidence=90 means the P10 outcome (pessimistic
end) must satisfy the target — i.e. "90% of simulations meet the goal".
"""

from __future__ import annotations

import math
from copy import deepcopy

from zng_simulator.config.charger import ChargerVariant
from zng_simulator.config.scenario import Scenario
from zng_simulator.engine.orchestrator import run_engine
from zng_simulator.finance.dcf import build_dcf_table
from zng_simulator.models.field_data import PilotSizingResult


def find_minimum_fleet_size(
    scenario: Scenario,
    charger: ChargerVariant,
    target_metric: str = "positive_npv",
    target_confidence_pct: float = 50.0,
    min_fleet: int = 10,
    max_fleet: int = 2000,
    max_iterations: int = 30,
    break_even_target_months: int | None = None,
) -> PilotSizingResult:
    """Binary-search for the minimum fleet size that achieves a financial target.

    Parameters
    ----------
    scenario : Scenario
        Base scenario (fleet size will be varied).
    charger : ChargerVariant
        Charger variant to evaluate.
    target_metric : str
        What to optimize for:
          - ``'positive_ncf'`` : total net cash flow > 0
          - ``'positive_npv'`` : NPV > 0 (DCF-adjusted)
          - ``'break_even_within'`` : break-even month ≤ ``break_even_target_months``
    target_confidence_pct : float
        Confidence level (0–100).  For stochastic engine:
          - 50 = median (P50) must meet target
          - 90 = P10 must meet target (90% of runs succeed)
          For static engine, this is ignored (deterministic = 100%).
    min_fleet : int
        Lower bound of fleet size search.
    max_fleet : int
        Upper bound of fleet size search.
    max_iterations : int
        Maximum binary search steps.
    break_even_target_months : int | None
        Required for ``target_metric='break_even_within'``.

    Returns
    -------
    PilotSizingResult
        Recommended fleet size with supporting metrics.
    """
    if target_metric == "break_even_within" and break_even_target_months is None:
        break_even_target_months = scenario.simulation.horizon_months

    search_log: list[dict] = []
    best_passing: int | None = None
    best_npv: float | None = None
    best_be: int | None = None
    best_ncf: float | None = None
    iterations = 0

    lo, hi = min_fleet, max_fleet

    while lo <= hi and iterations < max_iterations:
        mid = (lo + hi) // 2
        iterations += 1

        npv, ncf, be_month = _evaluate_fleet_size(
            scenario, charger, mid, target_confidence_pct,
        )

        passed = _check_target(target_metric, npv, ncf, be_month, break_even_target_months)

        search_log.append({
            "fleet_size": mid,
            "npv": round(npv, 2) if npv is not None else None,
            "ncf": round(ncf, 2) if ncf is not None else None,
            "break_even_month": be_month,
            "passed": passed,
        })

        if passed:
            best_passing = mid
            best_npv = npv
            best_be = be_month
            best_ncf = ncf
            hi = mid - 1  # try smaller
        else:
            lo = mid + 1  # need bigger

    achieved = best_passing is not None
    recommended = best_passing if achieved else max_fleet

    # Compute recommended stations/docks based on the fleet size
    docks_per_station = scenario.station.docks_per_station
    num_stations = scenario.station.num_stations

    return PilotSizingResult(
        recommended_fleet_size=recommended,
        recommended_num_stations=num_stations,
        recommended_docks_per_station=docks_per_station,
        target_confidence_pct=target_confidence_pct,
        target_metric=target_metric,
        achieved=achieved,
        best_npv=round(best_npv, 2) if best_npv is not None else None,
        best_break_even_month=best_be,
        best_monthly_ncf_at_target=(
            round(best_ncf / scenario.simulation.horizon_months, 2)
            if best_ncf is not None and scenario.simulation.horizon_months > 0
            else None
        ),
        search_iterations=iterations,
        search_log=search_log,
    )


def _evaluate_fleet_size(
    scenario: Scenario,
    charger: ChargerVariant,
    fleet_size: int,
    confidence_pct: float,
) -> tuple[float | None, float | None, int | None]:
    """Run the engine at a given fleet size and return (npv, ncf, break_even).

    For stochastic engine with Monte Carlo:
      - confidence_pct=50 → use P50 (median) metrics
      - confidence_pct=90 → use P10 (pessimistic) metrics
      i.e. percentile_used = 100 - confidence_pct

    For static engine:
      - Ignore confidence_pct (deterministic)
    """
    trial = deepcopy(scenario)
    trial.revenue.initial_fleet_size = fleet_size

    result = run_engine(trial, charger)

    # Compute DCF / NPV
    salvage = result.derived.total_packs * trial.pack.second_life_salvage_value
    dcf = build_dcf_table(
        result.months, result.summary, trial.finance,
        trial.simulation.discount_rate_annual, salvage,
    )

    if result.monte_carlo is not None:
        # Stochastic with Monte Carlo
        # P10 = pessimistic for NCF, so at confidence 90, use P10
        # At confidence 50, use P50 (median)
        if confidence_pct >= 90:
            ncf = result.monte_carlo.ncf_p10
            be = result.monte_carlo.break_even_p10
        elif confidence_pct >= 50:
            ncf = result.monte_carlo.ncf_p50
            be = result.monte_carlo.break_even_p50
        else:
            ncf = result.monte_carlo.ncf_p90
            be = result.monte_carlo.break_even_p90

        # NPV: use the DCF from the representative (P50) run
        # but scale conservatively based on confidence
        npv = dcf.npv
        return npv, ncf, be
    else:
        # Static or single stochastic
        npv = dcf.npv
        ncf = result.summary.total_net_cash_flow
        be = result.summary.break_even_month
        return npv, ncf, be


def _check_target(
    target_metric: str,
    npv: float | None,
    ncf: float | None,
    be_month: int | None,
    break_even_target: int | None,
) -> bool:
    """Check whether the target metric is satisfied."""
    if target_metric == "positive_npv":
        return npv is not None and npv > 0

    if target_metric == "positive_ncf":
        return ncf is not None and ncf > 0

    if target_metric == "break_even_within":
        if be_month is None or break_even_target is None:
            return False
        return be_month <= break_even_target

    return False


def find_optimal_scale(
    scenario: Scenario,
    charger: ChargerVariant,
    fleet_sizes: list[int] | None = None,
    target_metric: str = "positive_npv",
    target_confidence_pct: float = 50.0,
) -> PilotSizingResult:
    """Evaluate specific fleet sizes and return the best.

    Unlike ``find_minimum_fleet_size`` (binary search), this evaluates
    a given list of candidate fleet sizes and returns the one that
    maximizes NPV while meeting the target.

    Useful for scenario comparison: "Should we start with 100, 200, or 500 vehicles?"

    Parameters
    ----------
    scenario : Scenario
        Base scenario.
    charger : ChargerVariant
        Charger variant.
    fleet_sizes : list[int] | None
        Specific fleet sizes to evaluate.  Default: [50, 100, 200, 300, 500].
    target_metric : str
        Same as ``find_minimum_fleet_size``.
    target_confidence_pct : float
        Same as ``find_minimum_fleet_size``.

    Returns
    -------
    PilotSizingResult
        Best fleet size from the evaluated set.
    """
    if fleet_sizes is None:
        fleet_sizes = [50, 100, 200, 300, 500]

    search_log: list[dict] = []
    best_fleet = None
    best_npv_val: float | None = None
    best_be: int | None = None
    best_ncf: float | None = None

    for fs in fleet_sizes:
        npv, ncf, be_month = _evaluate_fleet_size(
            scenario, charger, fs, target_confidence_pct,
        )
        passed = _check_target(target_metric, npv, ncf, be_month, scenario.simulation.horizon_months)

        search_log.append({
            "fleet_size": fs,
            "npv": round(npv, 2) if npv is not None else None,
            "ncf": round(ncf, 2) if ncf is not None else None,
            "break_even_month": be_month,
            "passed": passed,
        })

        if passed:
            if best_npv_val is None or (npv is not None and npv > best_npv_val):
                best_fleet = fs
                best_npv_val = npv
                best_be = be_month
                best_ncf = ncf

    achieved = best_fleet is not None

    return PilotSizingResult(
        recommended_fleet_size=best_fleet if achieved else fleet_sizes[-1],
        recommended_num_stations=scenario.station.num_stations,
        recommended_docks_per_station=scenario.station.docks_per_station,
        target_confidence_pct=target_confidence_pct,
        target_metric=target_metric,
        achieved=achieved,
        best_npv=round(best_npv_val, 2) if best_npv_val is not None else None,
        best_break_even_month=best_be,
        best_monthly_ncf_at_target=(
            round(best_ncf / scenario.simulation.horizon_months, 2)
            if best_ncf is not None and scenario.simulation.horizon_months > 0
            else None
        ),
        search_iterations=len(fleet_sizes),
        search_log=search_log,
    )
