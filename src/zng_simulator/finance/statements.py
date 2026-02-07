"""Financial statements — P&L and Cash Flow Statement (§7.1).

Transforms raw engine snapshots into investor-grade financial statements:
  - P&L: Revenue → EBITDA → EBIT → EBT → Net Income
  - Cash Flow Statement: Operating + Investing + Financing = Net CF

All figures are monthly.  Depreciation is applied per the chosen method.
"""

from __future__ import annotations

from zng_simulator.config.battery import PackSpec
from zng_simulator.config.charger import ChargerVariant
from zng_simulator.config.finance import FinanceConfig
from zng_simulator.config.opex import OpExConfig
from zng_simulator.config.station import StationConfig
from zng_simulator.models.results import (
    DebtSchedule,
    FinancialStatements,
    MonthlyCashFlowStatement,
    MonthlyPnL,
    MonthlySnapshot,
)


def _compute_monthly_depreciation(
    total_depreciable_assets: float,
    finance_cfg: FinanceConfig,
    month: int,
    book_value: float,
) -> float:
    """Compute depreciation for one month.

    Straight-line: total_assets / useful_life_months
    WDV: annual_rate × book_value / 12
    """
    if month > finance_cfg.asset_useful_life_months:
        return 0.0  # Fully depreciated
    if finance_cfg.depreciation_method == "straight_line":
        return total_depreciable_assets / finance_cfg.asset_useful_life_months
    else:  # wdv
        monthly_rate = finance_cfg.wdv_rate_annual / 12
        return book_value * monthly_rate


def build_financial_statements(
    months: list[MonthlySnapshot],
    debt: DebtSchedule,
    finance_cfg: FinanceConfig,
    opex_cfg: OpExConfig,
    station_cfg: StationConfig,
    pack: PackSpec,
    charger: ChargerVariant,
    total_initial_capex: float,
) -> FinancialStatements:
    """Build monthly P&L and Cash Flow Statement.

    Parameters
    ----------
    months : list[MonthlySnapshot]
        Engine output snapshots.
    debt : DebtSchedule
        Debt schedule from dscr module.
    finance_cfg : FinanceConfig
        Depreciation, tax settings.
    opex_cfg : OpExConfig
        For electricity/labor decomposition.
    station_cfg : StationConfig
        For station count (used in OpEx breakdown).
    pack : PackSpec
        Battery pack spec (for electricity cost calculation).
    charger : ChargerVariant
        Charger variant (for efficiency in electricity cost calc).
    total_initial_capex : float
        Total depreciable asset base.
    """
    pnl_list: list[MonthlyPnL] = []
    cf_list: list[MonthlyCashFlowStatement] = []

    debt_rows_by_month = {r.month: r for r in debt.rows}
    cumulative_cf = 0.0
    book_value = total_initial_capex  # for WDV depreciation

    for snap in months:
        m = snap.month

        # --- P&L ---
        revenue = snap.revenue

        # Decompose OpEx: electricity + labor (variable) vs station costs (fixed)
        eff = charger.charging_efficiency_pct if charger.charging_efficiency_pct > 0 else 0.90
        energy_per_cycle_kwh = pack.nominal_capacity_kwh / eff
        electricity = snap.total_cycles * energy_per_cycle_kwh * opex_cfg.electricity_tariff_per_kwh
        labor = snap.total_cycles * opex_cfg.pack_handling_labor_per_swap

        # Station-level fixed costs = total opex − variable costs
        station_opex = snap.opex_total - electricity - labor
        if station_opex < 0:
            # Guard: if engine opex is lower (rounding), keep it non-negative
            station_opex = max(station_opex, 0)

        gross_profit = revenue - electricity - labor
        ebitda = gross_profit - station_opex

        # Depreciation
        depreciation = _compute_monthly_depreciation(
            total_initial_capex, finance_cfg, m, book_value,
        )
        depreciation = min(depreciation, book_value)
        book_value = max(book_value - depreciation, 0)

        ebit = ebitda - depreciation

        # Interest from debt schedule
        debt_row = debt_rows_by_month.get(m)
        interest = debt_row.interest if debt_row else 0.0

        ebt = ebit - interest

        # Tax (only on positive income)
        tax = max(ebt, 0) * finance_cfg.tax_rate
        net_income = ebt - tax

        pnl_list.append(MonthlyPnL(
            month=m,
            revenue=round(revenue, 2),
            electricity_cost=round(electricity, 2),
            labor_cost=round(labor, 2),
            gross_profit=round(gross_profit, 2),
            station_opex=round(station_opex, 2),
            ebitda=round(ebitda, 2),
            depreciation=round(depreciation, 2),
            ebit=round(ebit, 2),
            interest=round(interest, 2),
            ebt=round(ebt, 2),
            tax=round(tax, 2),
            net_income=round(net_income, 2),
        ))

        # --- Cash Flow Statement ---
        operating_cf = revenue - snap.opex_total  # cash OpEx (no depreciation)
        investing_cf = -snap.capex_this_month

        # Financing CF: debt drawdown in month 1, minus EMI thereafter
        if m == 1:
            financing_cf = debt.loan_amount  # inflow
        else:
            financing_cf = 0.0

        if debt_row:
            financing_cf -= debt_row.emi  # outflow

        net_cf = operating_cf + investing_cf + financing_cf
        cumulative_cf += net_cf

        cf_list.append(MonthlyCashFlowStatement(
            month=m,
            operating_cf=round(operating_cf, 2),
            investing_cf=round(investing_cf, 2),
            financing_cf=round(financing_cf, 2),
            net_cf=round(net_cf, 2),
            cumulative_cf=round(cumulative_cf, 2),
        ))

    return FinancialStatements(pnl=pnl_list, cash_flow=cf_list)
