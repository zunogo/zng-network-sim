"""Debt schedule & DSCR — Phase 3 (§7.2).

Models the debt side of the capital structure:
  - EMI amortization with grace period
  - Monthly DSCR = NOI / debt_service
  - SLB feasibility indicators

Key formulas:
  loan_amount = total_initial_capex × debt_pct_of_capex
  EMI = P × r × (1+r)^n / ((1+r)^n − 1)  where n = tenor − grace
  DSCR = (Revenue − OpEx) / (Interest + Principal)
"""

from __future__ import annotations

import math

from zng_simulator.config.finance import FinanceConfig
from zng_simulator.models.results import (
    DebtSchedule,
    DebtScheduleRow,
    DSCRResult,
    MonthlySnapshot,
)


def build_debt_schedule(
    total_initial_capex: float,
    finance_cfg: FinanceConfig,
    horizon_months: int,
) -> DebtSchedule:
    """Generate month-by-month debt amortization schedule.

    Parameters
    ----------
    total_initial_capex : float
        Total CapEx at month 0 (station + charger + packs).
    finance_cfg : FinanceConfig
        Debt structure inputs.
    horizon_months : int
        Simulation horizon (schedule runs for min(tenor, horizon) months).

    Returns
    -------
    DebtSchedule
        Full amortization schedule.
    """
    loan = total_initial_capex * finance_cfg.debt_pct_of_capex
    if loan <= 0:
        return DebtSchedule(
            loan_amount=0, monthly_rate=0, rows=[],
            total_interest_paid=0, total_principal_paid=0,
        )

    monthly_rate = finance_cfg.interest_rate_annual / 12
    grace = finance_cfg.grace_period_months
    tenor = finance_cfg.loan_tenor_months
    amort_months = tenor - grace  # months of principal + interest payments

    # EMI for the amortization period
    if monthly_rate > 0 and amort_months > 0:
        factor = (1 + monthly_rate) ** amort_months
        emi = loan * monthly_rate * factor / (factor - 1)
    elif amort_months > 0:
        emi = loan / amort_months
    else:
        emi = 0.0

    rows: list[DebtScheduleRow] = []
    balance = loan
    total_interest = 0.0
    total_principal = 0.0

    num_months = min(tenor, horizon_months)

    for m in range(1, num_months + 1):
        interest = balance * monthly_rate
        if m <= grace:
            # Grace period: interest-only
            principal = 0.0
            payment = interest
        else:
            # Amortization period: EMI
            principal = emi - interest
            principal = min(principal, balance)  # don't overshoot
            payment = interest + principal

        closing = balance - principal

        rows.append(DebtScheduleRow(
            month=m,
            opening_balance=round(balance, 2),
            interest=round(interest, 2),
            principal=round(principal, 2),
            emi=round(payment, 2),
            closing_balance=round(max(closing, 0), 2),
        ))

        total_interest += interest
        total_principal += principal
        balance = max(closing, 0)

    return DebtSchedule(
        loan_amount=round(loan, 2),
        monthly_rate=round(monthly_rate, 6),
        rows=rows,
        total_interest_paid=round(total_interest, 2),
        total_principal_paid=round(total_principal, 2),
    )


def compute_dscr(
    months: list[MonthlySnapshot],
    debt: DebtSchedule,
    finance_cfg: FinanceConfig,
    remaining_asset_value: float | None = None,
) -> DSCRResult:
    """Compute monthly DSCR from simulation results and debt schedule.

    DSCR = Net Operating Income / Total Debt Service
    NOI  = Revenue − OpEx (before CapEx and debt service)

    Parameters
    ----------
    months : list[MonthlySnapshot]
        Monthly snapshots from engine.
    debt : DebtSchedule
        Debt amortization schedule.
    finance_cfg : FinanceConfig
        For covenant threshold.
    remaining_asset_value : float | None
        Total asset value at horizon end (for asset cover ratio).
    """
    if debt.loan_amount <= 0 or not debt.rows:
        return DSCRResult(
            monthly_dscr=[],
            avg_dscr=float("inf"),
            min_dscr=float("inf"),
            min_dscr_month=0,
            breach_months=[],
            covenant_threshold=finance_cfg.dscr_covenant_threshold,
            asset_cover_ratio=None,
        )

    monthly_dscr: list[float] = []
    breach_months: list[int] = []
    debt_rows_by_month = {r.month: r for r in debt.rows}

    for snap in months:
        m = snap.month
        noi = snap.revenue - snap.opex_total

        debt_row = debt_rows_by_month.get(m)
        if debt_row and debt_row.emi > 0:
            dscr_val = noi / debt_row.emi
        else:
            dscr_val = float("inf")  # no debt service this month

        monthly_dscr.append(round(dscr_val, 4))

        if dscr_val < finance_cfg.dscr_covenant_threshold and dscr_val != float("inf"):
            breach_months.append(m)

    # Filter out inf values for statistics
    finite_dscr = [d for d in monthly_dscr if d != float("inf") and not math.isinf(d)]

    avg = sum(finite_dscr) / len(finite_dscr) if finite_dscr else float("inf")
    min_val = min(finite_dscr) if finite_dscr else float("inf")
    min_month = monthly_dscr.index(min_val) + 1 if finite_dscr else 0

    # Asset cover ratio
    acr = None
    if remaining_asset_value is not None and debt.rows:
        last_balance = debt.rows[-1].closing_balance
        if last_balance > 0:
            acr = round(remaining_asset_value / last_balance, 4)

    return DSCRResult(
        monthly_dscr=monthly_dscr,
        avg_dscr=round(avg, 4),
        min_dscr=round(min_val, 4),
        min_dscr_month=min_month,
        breach_months=breach_months,
        covenant_threshold=finance_cfg.dscr_covenant_threshold,
        asset_cover_ratio=acr,
    )
