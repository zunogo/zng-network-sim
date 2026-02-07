"""DCF engine — NPV, IRR, terminal value, discounted payback (§7.1).

Takes monthly cash flows from any engine run and applies time-value-of-money.
This is the core of Phase 3 — it transforms operational outputs into
investor-grade financial metrics.

Key formulas:
  NPV = Σ CF_t / (1 + r_monthly)^t  + PV(terminal_value)
  IRR = rate where NPV = 0  (Newton-Raphson bisection)
  Discounted payback = first month where cumulative PV(CF) ≥ 0
"""

from __future__ import annotations

from zng_simulator.config.finance import FinanceConfig
from zng_simulator.models.results import (
    DCFResult,
    MonthlyDCFRow,
    MonthlySnapshot,
    RunSummary,
)


def compute_npv(cash_flows: list[float], annual_rate: float) -> float:
    """Compute Net Present Value of monthly cash flows.

    Parameters
    ----------
    cash_flows : list[float]
        Monthly net cash flows. Index 0 = month 1.
    annual_rate : float
        Annual discount rate (e.g. 0.12 for 12%).

    Returns
    -------
    float
        NPV = Σ CF_t / (1 + r_monthly)^t
    """
    if not cash_flows:
        return 0.0

    r_monthly = (1 + annual_rate) ** (1 / 12) - 1
    npv = 0.0
    for t, cf in enumerate(cash_flows, start=1):
        npv += cf / (1 + r_monthly) ** t
    return npv


def compute_irr(cash_flows: list[float], max_iter: int = 200, tol: float = 1e-8) -> float | None:
    """Compute Internal Rate of Return (annual) via bisection.

    Searches for the annual rate where NPV = 0.

    Returns None if:
      - All cash flows are same sign (no crossover)
      - Convergence fails within max_iter
    """
    if not cash_flows or len(cash_flows) < 2:
        return None

    # Quick check: need at least one sign change
    has_positive = any(cf > 0 for cf in cash_flows)
    has_negative = any(cf < 0 for cf in cash_flows)
    if not (has_positive and has_negative):
        return None

    # Bisection between -50% and 1000% annual
    low, high = -0.50, 10.0

    for _ in range(max_iter):
        mid = (low + high) / 2
        npv_mid = compute_npv(cash_flows, mid)

        if abs(npv_mid) < tol:
            return mid

        # Check sign of NPV at low to determine direction
        npv_low = compute_npv(cash_flows, low)

        if npv_low * npv_mid < 0:
            high = mid
        else:
            low = mid

        if high - low < tol:
            return mid

    return (low + high) / 2


def compute_terminal_value(
    config: FinanceConfig,
    last_year_ncf: float,
    total_salvage: float,
    annual_discount_rate: float,
    horizon_months: int,
) -> float:
    """Compute terminal value at horizon end, in present-value terms.

    Methods:
      - 'salvage': total_salvage discounted to present
      - 'gordon_growth': NCF × (1+g) / (r−g) discounted to present
      - 'none': 0
    """
    if config.terminal_value_method == "none":
        return 0.0

    r_monthly = (1 + annual_discount_rate) ** (1 / 12) - 1
    discount_to_present = 1 / (1 + r_monthly) ** horizon_months

    if config.terminal_value_method == "salvage":
        return total_salvage * discount_to_present

    if config.terminal_value_method == "gordon_growth":
        r = annual_discount_rate
        g = config.terminal_growth_rate
        if r <= g:
            # Gordon growth model invalid when r ≤ g — fall back to salvage
            return total_salvage * discount_to_present
        perpetuity = last_year_ncf * (1 + g) / (r - g)
        return perpetuity * discount_to_present

    return 0.0


def compute_discounted_payback(cash_flows: list[float], annual_rate: float) -> int | None:
    """First month where cumulative PV(CF) ≥ 0.

    Returns None if never breaks even in the given horizon.
    """
    if not cash_flows:
        return None

    r_monthly = (1 + annual_rate) ** (1 / 12) - 1
    cumulative_pv = 0.0
    for t, cf in enumerate(cash_flows, start=1):
        cumulative_pv += cf / (1 + r_monthly) ** t
        if cumulative_pv >= 0 and t > 1:
            return t
    return None


def build_dcf_table(
    months: list[MonthlySnapshot],
    summary: RunSummary,
    finance_cfg: FinanceConfig,
    annual_discount_rate: float,
    total_salvage: float = 0.0,
) -> DCFResult:
    """Build full DCF analysis from simulation results.

    Parameters
    ----------
    months : list[MonthlySnapshot]
        Monthly cash flow snapshots from the engine.
    summary : RunSummary
        Aggregated run summary.
    finance_cfg : FinanceConfig
        Financial assumptions (terminal value, etc.).
    annual_discount_rate : float
        WACC / discount rate.
    total_salvage : float
        Total salvage value of all assets at horizon end.
    """
    cash_flows = [m.net_cash_flow for m in months]
    horizon = len(months)

    r_monthly = (1 + annual_discount_rate) ** (1 / 12) - 1

    # Monthly DCF rows
    dcf_rows: list[MonthlyDCFRow] = []
    cumulative_pv = 0.0
    for t, cf in enumerate(cash_flows, start=1):
        df = 1 / (1 + r_monthly) ** t
        pv = cf * df
        cumulative_pv += pv
        dcf_rows.append(MonthlyDCFRow(
            month=t,
            discount_factor=round(df, 6),
            nominal_net_cf=round(cf, 2),
            pv_net_cf=round(pv, 2),
            cumulative_pv=round(cumulative_pv, 2),
        ))

    # Terminal value
    last_year_ncf = sum(cf for cf in cash_flows[-12:]) if horizon >= 12 else sum(cash_flows)
    tv = compute_terminal_value(finance_cfg, last_year_ncf, total_salvage, annual_discount_rate, horizon)

    # NPV = cumulative PV + terminal value
    npv = cumulative_pv + tv

    # IRR
    # Add terminal value as a final cash flow for IRR computation
    irr_flows = list(cash_flows)
    if tv > 0:
        irr_flows[-1] += tv / (1 / (1 + r_monthly) ** horizon)  # un-discount TV for IRR calc
    irr = compute_irr(irr_flows)

    # Discounted payback
    payback = compute_discounted_payback(cash_flows, annual_discount_rate)

    return DCFResult(
        npv=round(npv, 2),
        irr=round(irr, 4) if irr is not None else None,
        discounted_payback_month=payback,
        terminal_value=round(tv, 2),
        monthly_dcf=dcf_rows,
        undiscounted_total=round(sum(cash_flows), 2),
    )
