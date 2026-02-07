"""Tests for debt schedule and DSCR (Phase 3)."""

import pytest
from zng_simulator.finance.dscr import build_debt_schedule, compute_dscr
from zng_simulator.config.finance import FinanceConfig
from zng_simulator.models.results import MonthlySnapshot, CostPerCycleWaterfall


def _dummy_cpc() -> CostPerCycleWaterfall:
    return CostPerCycleWaterfall(
        battery=1, charger=1, electricity=1, real_estate=1,
        maintenance=1, insurance=1, sabotage=0, logistics=1, overhead=1, total=8,
    )


def _make_snapshots(count: int, revenue: float = 200000, opex: float = 100000) -> list[MonthlySnapshot]:
    snapshots = []
    cumulative = 0.0
    for i in range(1, count + 1):
        ncf = revenue - opex - (500000 if i == 1 else 0)
        cumulative += ncf
        snapshots.append(MonthlySnapshot(
            month=i, fleet_size=100, swap_visits=100, total_cycles=200,
            revenue=revenue, opex_total=opex,
            capex_this_month=500000 if i == 1 else 0,
            net_cash_flow=ncf, cumulative_cash_flow=cumulative,
            cost_per_cycle=_dummy_cpc(),
        ))
    return snapshots


class TestBuildDebtSchedule:
    def test_basic_schedule(self):
        cfg = FinanceConfig(
            debt_pct_of_capex=0.70, interest_rate_annual=0.12,
            loan_tenor_months=60, grace_period_months=6,
        )
        sched = build_debt_schedule(1_000_000, cfg, 60)

        assert sched.loan_amount == 700_000
        assert len(sched.rows) == 60
        assert sched.total_principal_paid == pytest.approx(700_000, abs=100)

    def test_grace_period_no_principal(self):
        cfg = FinanceConfig(
            debt_pct_of_capex=0.50, interest_rate_annual=0.12,
            loan_tenor_months=24, grace_period_months=6,
        )
        sched = build_debt_schedule(1_000_000, cfg, 24)

        for row in sched.rows[:6]:
            assert row.principal == 0  # Grace period
            assert row.interest > 0

        for row in sched.rows[6:]:
            assert row.principal > 0  # Amortization

    def test_zero_debt(self):
        cfg = FinanceConfig(debt_pct_of_capex=0)
        sched = build_debt_schedule(1_000_000, cfg, 60)

        assert sched.loan_amount == 0
        assert sched.rows == []
        assert sched.total_interest_paid == 0

    def test_closing_balance_decreases(self):
        cfg = FinanceConfig(
            debt_pct_of_capex=0.70, interest_rate_annual=0.12,
            loan_tenor_months=60, grace_period_months=0,
        )
        sched = build_debt_schedule(1_000_000, cfg, 60)

        # After grace, closing balance should decrease
        for i in range(1, len(sched.rows)):
            assert sched.rows[i].closing_balance <= sched.rows[i-1].closing_balance

    def test_final_balance_near_zero(self):
        cfg = FinanceConfig(
            debt_pct_of_capex=1.0, interest_rate_annual=0.10,
            loan_tenor_months=60, grace_period_months=0,
        )
        sched = build_debt_schedule(1_000_000, cfg, 60)
        assert sched.rows[-1].closing_balance < 1  # ~0


class TestComputeDSCR:
    def test_basic_dscr(self):
        cfg = FinanceConfig(
            debt_pct_of_capex=0.70, interest_rate_annual=0.12,
            loan_tenor_months=60, grace_period_months=6,
            dscr_covenant_threshold=1.20,
        )
        snapshots = _make_snapshots(60)
        sched = build_debt_schedule(1_000_000, cfg, 60)

        dscr = compute_dscr(snapshots, sched, cfg)

        assert len(dscr.monthly_dscr) == 60
        assert dscr.avg_dscr > 0
        assert dscr.min_dscr > 0
        assert dscr.min_dscr <= dscr.avg_dscr
        assert dscr.covenant_threshold == 1.20

    def test_no_debt_dscr(self):
        cfg = FinanceConfig(debt_pct_of_capex=0)
        snapshots = _make_snapshots(60)
        sched = build_debt_schedule(1_000_000, cfg, 60)

        dscr = compute_dscr(snapshots, sched, cfg)

        assert dscr.monthly_dscr == []
        assert dscr.breach_months == []

    def test_breach_detection(self):
        cfg = FinanceConfig(
            debt_pct_of_capex=0.90, interest_rate_annual=0.20,
            loan_tenor_months=60, grace_period_months=0,
            dscr_covenant_threshold=5.0,  # Very high threshold
        )
        snapshots = _make_snapshots(60, revenue=150000, opex=100000)
        sched = build_debt_schedule(1_000_000, cfg, 60)

        dscr = compute_dscr(snapshots, sched, cfg)
        assert len(dscr.breach_months) > 0  # Should have breaches

    def test_asset_cover_ratio(self):
        """Run only 36 of a 60-month loan → remaining balance > 0."""
        cfg = FinanceConfig(
            debt_pct_of_capex=0.70, interest_rate_annual=0.12,
            loan_tenor_months=60, grace_period_months=0,
        )
        snapshots = _make_snapshots(36)
        sched = build_debt_schedule(1_000_000, cfg, 36)

        dscr = compute_dscr(snapshots, sched, cfg, remaining_asset_value=500_000)
        assert dscr.asset_cover_ratio is not None
        assert dscr.asset_cover_ratio > 0
