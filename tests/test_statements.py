"""Tests for financial statements — P&L and Cash Flow (Phase 3)."""

import pytest
from zng_simulator.finance.statements import build_financial_statements
from zng_simulator.finance.dscr import build_debt_schedule
from zng_simulator.config.finance import FinanceConfig
from zng_simulator.config.opex import OpExConfig
from zng_simulator.config.station import StationConfig
from zng_simulator.config.battery import PackSpec
from zng_simulator.config.charger import ChargerVariant
from zng_simulator.models.results import MonthlySnapshot, CostPerCycleWaterfall


def _dummy_cpc() -> CostPerCycleWaterfall:
    return CostPerCycleWaterfall(
        battery=1, charger=1, electricity=1, real_estate=1,
        maintenance=1, insurance=1, sabotage=0, logistics=1, overhead=1, total=8,
    )


@pytest.fixture
def basic_snapshots() -> list[MonthlySnapshot]:
    snapshots = []
    cumulative = 0.0
    for i in range(1, 61):
        rev = 200_000
        opex = 100_000
        capex = 500_000 if i == 1 else 0
        ncf = rev - opex - capex
        cumulative += ncf
        snapshots.append(MonthlySnapshot(
            month=i, fleet_size=100, swap_visits=500, total_cycles=1000,
            revenue=rev, opex_total=opex,
            capex_this_month=capex,
            net_cash_flow=ncf, cumulative_cash_flow=cumulative,
            cost_per_cycle=_dummy_cpc(),
        ))
    return snapshots


@pytest.fixture
def finance_cfg() -> FinanceConfig:
    return FinanceConfig(
        debt_pct_of_capex=0.70, interest_rate_annual=0.12,
        loan_tenor_months=60, grace_period_months=6,
        depreciation_method="straight_line", asset_useful_life_months=60,
        tax_rate=0.25,
    )


@pytest.fixture
def opex_c() -> OpExConfig:
    return OpExConfig(
        electricity_tariff_per_kwh=8.0,
        pack_handling_labor_per_swap=2.0,
    )


@pytest.fixture
def station_c() -> StationConfig:
    return StationConfig(num_stations=5, docks_per_station=8)


@pytest.fixture
def pack_c() -> PackSpec:
    return PackSpec(nominal_capacity_kwh=1.28)


@pytest.fixture
def charger_c() -> ChargerVariant:
    return ChargerVariant(charging_efficiency_pct=0.90)


class TestPnL:
    def test_pnl_length(self, basic_snapshots, finance_cfg, opex_c, station_c, pack_c, charger_c):
        debt = build_debt_schedule(500_000, finance_cfg, 60)
        stmts = build_financial_statements(
            basic_snapshots, debt, finance_cfg, opex_c, station_c, pack_c, charger_c, 500_000,
        )
        assert len(stmts.pnl) == 60

    def test_pnl_components(self, basic_snapshots, finance_cfg, opex_c, station_c, pack_c, charger_c):
        debt = build_debt_schedule(500_000, finance_cfg, 60)
        stmts = build_financial_statements(
            basic_snapshots, debt, finance_cfg, opex_c, station_c, pack_c, charger_c, 500_000,
        )
        row = stmts.pnl[0]
        assert row.month == 1
        assert row.revenue == 200_000
        assert row.gross_profit == row.revenue - row.electricity_cost - row.labor_cost
        assert row.ebitda == row.gross_profit - row.station_opex
        assert row.ebit == row.ebitda - row.depreciation
        assert row.ebt == row.ebit - row.interest
        if row.ebt > 0:
            assert row.tax == pytest.approx(row.ebt * 0.25, abs=1)
        assert row.net_income == pytest.approx(row.ebt - row.tax, abs=1)

    def test_depreciation_straight_line(self, basic_snapshots, finance_cfg, opex_c, station_c, pack_c, charger_c):
        debt = build_debt_schedule(500_000, finance_cfg, 60)
        stmts = build_financial_statements(
            basic_snapshots, debt, finance_cfg, opex_c, station_c, pack_c, charger_c, 500_000,
        )
        expected_depr = 500_000 / 60
        assert stmts.pnl[0].depreciation == pytest.approx(expected_depr, abs=1)
        assert stmts.pnl[30].depreciation == pytest.approx(expected_depr, abs=1)

    def test_depreciation_wdv(self, basic_snapshots, opex_c, station_c, pack_c, charger_c):
        cfg = FinanceConfig(
            depreciation_method="wdv", wdv_rate_annual=0.25,
            debt_pct_of_capex=0, asset_useful_life_months=60,
        )
        debt = build_debt_schedule(500_000, cfg, 60)
        stmts = build_financial_statements(
            basic_snapshots, debt, cfg, opex_c, station_c, pack_c, charger_c, 500_000,
        )
        # WDV: first month depr = 500000 * 0.25 / 12
        expected_first = 500_000 * 0.25 / 12
        assert stmts.pnl[0].depreciation == pytest.approx(expected_first, abs=1)
        # Subsequent months should decrease
        assert stmts.pnl[1].depreciation < stmts.pnl[0].depreciation


class TestCashFlowStatement:
    def test_cf_length(self, basic_snapshots, finance_cfg, opex_c, station_c, pack_c, charger_c):
        debt = build_debt_schedule(500_000, finance_cfg, 60)
        stmts = build_financial_statements(
            basic_snapshots, debt, finance_cfg, opex_c, station_c, pack_c, charger_c, 500_000,
        )
        assert len(stmts.cash_flow) == 60

    def test_cf_month1_debt_drawdown(self, basic_snapshots, finance_cfg, opex_c, station_c, pack_c, charger_c):
        debt = build_debt_schedule(500_000, finance_cfg, 60)
        stmts = build_financial_statements(
            basic_snapshots, debt, finance_cfg, opex_c, station_c, pack_c, charger_c, 500_000,
        )
        cf1 = stmts.cash_flow[0]
        # Month 1 financing = loan_amount - EMI(month 1)
        assert cf1.financing_cf > 0  # net positive from drawdown
        assert cf1.investing_cf == -500_000  # initial CapEx

    def test_cf_components_add_up(self, basic_snapshots, finance_cfg, opex_c, station_c, pack_c, charger_c):
        debt = build_debt_schedule(500_000, finance_cfg, 60)
        stmts = build_financial_statements(
            basic_snapshots, debt, finance_cfg, opex_c, station_c, pack_c, charger_c, 500_000,
        )
        for cf in stmts.cash_flow:
            expected_net = cf.operating_cf + cf.investing_cf + cf.financing_cf
            assert cf.net_cf == pytest.approx(expected_net, abs=1)

    def test_cumulative_cf(self, basic_snapshots, finance_cfg, opex_c, station_c, pack_c, charger_c):
        debt = build_debt_schedule(500_000, finance_cfg, 60)
        stmts = build_financial_statements(
            basic_snapshots, debt, finance_cfg, opex_c, station_c, pack_c, charger_c, 500_000,
        )
        running = 0.0
        for cf in stmts.cash_flow:
            running += cf.net_cf
            assert cf.cumulative_cf == pytest.approx(running, abs=1)

    def test_no_debt_financing(self, basic_snapshots, opex_c, station_c, pack_c, charger_c):
        cfg = FinanceConfig(debt_pct_of_capex=0)
        debt = build_debt_schedule(500_000, cfg, 60)
        stmts = build_financial_statements(
            basic_snapshots, debt, cfg, opex_c, station_c, pack_c, charger_c, 500_000,
        )
        # No debt → financing CF = 0 every month
        for cf in stmts.cash_flow:
            assert cf.financing_cf == 0
