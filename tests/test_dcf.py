"""Tests for DCF engine — NPV, IRR, discounted payback (Phase 3)."""

import pytest
from zng_simulator.finance.dcf import (
    compute_npv,
    compute_irr,
    compute_discounted_payback,
    compute_terminal_value,
    build_dcf_table,
)
from zng_simulator.config.finance import FinanceConfig
from zng_simulator.models.results import MonthlySnapshot, RunSummary, CostPerCycleWaterfall


# ── Helpers ─────────────────────────────────────────────────────────────────

def _dummy_cpc() -> CostPerCycleWaterfall:
    return CostPerCycleWaterfall(
        battery=1, charger=1, electricity=1, real_estate=1,
        maintenance=1, insurance=1, sabotage=0, logistics=1, overhead=1, total=8,
    )


def _make_snapshots(monthly_cfs: list[float]) -> list[MonthlySnapshot]:
    """Create minimal MonthlySnapshot objects from a list of net cash flows."""
    snapshots = []
    cumulative = 0.0
    for i, ncf in enumerate(monthly_cfs, start=1):
        cumulative += ncf
        snapshots.append(MonthlySnapshot(
            month=i, fleet_size=100, swap_visits=100, total_cycles=200,
            revenue=max(ncf + 100000, 0), opex_total=100000,
            capex_this_month=100000 if i == 1 else 0,
            net_cash_flow=ncf, cumulative_cash_flow=cumulative,
            cost_per_cycle=_dummy_cpc(),
        ))
    return snapshots


def _make_summary(snapshots: list[MonthlySnapshot]) -> RunSummary:
    total_rev = sum(s.revenue for s in snapshots)
    total_opex = sum(s.opex_total for s in snapshots)
    total_capex = sum(s.capex_this_month for s in snapshots)
    return RunSummary(
        charger_variant_name="Test",
        total_revenue=total_rev,
        total_opex=total_opex,
        total_capex=total_capex,
        total_net_cash_flow=total_rev - total_opex - total_capex,
        avg_cost_per_cycle=8.0,
        break_even_month=None,
    )


# ── NPV tests ──────────────────────────────────────────────────────────────

class TestComputeNPV:
    def test_zero_rate(self):
        """At 0% discount, NPV = sum of cash flows."""
        cfs = [100.0, 200.0, 300.0]
        assert compute_npv(cfs, 0.0) == pytest.approx(600.0, abs=0.01)

    def test_positive_rate_reduces_npv(self):
        """Positive discount reduces NPV below simple sum."""
        cfs = [100.0, 100.0, 100.0]
        npv = compute_npv(cfs, 0.12)
        assert npv < 300.0
        assert npv > 0

    def test_empty_flows(self):
        assert compute_npv([], 0.12) == 0.0

    def test_single_flow(self):
        """Single month cash flow at 12% annual."""
        npv = compute_npv([1000.0], 0.12)
        r_m = (1.12) ** (1/12) - 1
        expected = 1000 / (1 + r_m)
        assert npv == pytest.approx(expected, rel=1e-4)

    def test_negative_flows(self):
        """NPV of all-negative flows is negative."""
        cfs = [-100.0, -200.0, -300.0]
        assert compute_npv(cfs, 0.12) < 0


# ── IRR tests ──────────────────────────────────────────────────────────────

class TestComputeIRR:
    def test_basic_irr(self):
        """Simple scenario: big outflow then equal inflows."""
        cfs = [-100000] + [5000] * 60
        irr = compute_irr(cfs)
        assert irr is not None
        assert irr > 0  # profitable project

    def test_no_sign_change_returns_none(self):
        """All positive flows → no IRR."""
        cfs = [100] * 10
        assert compute_irr(cfs) is None

    def test_all_negative_returns_none(self):
        cfs = [-100] * 10
        assert compute_irr(cfs) is None

    def test_empty_returns_none(self):
        assert compute_irr([]) is None

    def test_irr_at_zero_npv(self):
        """IRR should make NPV ≈ 0."""
        cfs = [-100000] + [5000] * 60
        irr = compute_irr(cfs)
        if irr is not None:
            npv = compute_npv(cfs, irr)
            assert abs(npv) < 100  # close to zero


# ── Discounted payback ─────────────────────────────────────────────────────

class TestDiscountedPayback:
    def test_basic_payback(self):
        """CapEx in month 1, then positive inflows → eventual payback."""
        cfs = [-500000] + [20000] * 59
        month = compute_discounted_payback(cfs, 0.12)
        assert month is not None
        assert month > 1

    def test_never_pays_back(self):
        """Insufficient inflows → None."""
        cfs = [-1000000] + [100] * 59
        month = compute_discounted_payback(cfs, 0.12)
        assert month is None

    def test_empty(self):
        assert compute_discounted_payback([], 0.12) is None


# ── Terminal value ─────────────────────────────────────────────────────────

class TestTerminalValue:
    def test_salvage_method(self):
        cfg = FinanceConfig(terminal_value_method="salvage")
        tv = compute_terminal_value(cfg, 100000, 500000, 0.12, 60)
        assert tv > 0
        assert tv < 500000  # discounted

    def test_gordon_growth(self):
        cfg = FinanceConfig(terminal_value_method="gordon_growth", terminal_growth_rate=0.02)
        tv = compute_terminal_value(cfg, 100000, 0, 0.12, 60)
        assert tv > 0

    def test_none_method(self):
        cfg = FinanceConfig(terminal_value_method="none")
        tv = compute_terminal_value(cfg, 100000, 500000, 0.12, 60)
        assert tv == 0.0

    def test_gordon_invalid_rate(self):
        """r ≤ g → falls back to salvage."""
        cfg = FinanceConfig(terminal_value_method="gordon_growth", terminal_growth_rate=0.10)
        tv = compute_terminal_value(cfg, 100000, 200000, 0.08, 60)
        assert tv > 0  # should still produce a value (salvage fallback)


# ── Full DCF table ─────────────────────────────────────────────────────────

class TestBuildDCFTable:
    def test_basic_dcf(self):
        cfs = [-500000] + [20000] * 59
        snapshots = _make_snapshots(cfs)
        summary = _make_summary(snapshots)
        cfg = FinanceConfig(terminal_value_method="salvage")

        dcf = build_dcf_table(snapshots, summary, cfg, 0.12, total_salvage=200000)

        assert len(dcf.monthly_dcf) == 60
        assert dcf.monthly_dcf[0].month == 1
        assert dcf.monthly_dcf[0].discount_factor < 1.0
        assert dcf.terminal_value > 0
        assert dcf.undiscounted_total == pytest.approx(sum(cfs), abs=1)

    def test_dcf_npv_positive_project(self):
        """A clearly profitable project should have positive NPV."""
        cfs = [-200000] + [30000] * 59
        snapshots = _make_snapshots(cfs)
        summary = _make_summary(snapshots)
        cfg = FinanceConfig(terminal_value_method="none")

        dcf = build_dcf_table(snapshots, summary, cfg, 0.10)
        assert dcf.npv > 0

    def test_dcf_irr_exists(self):
        cfs = [-200000] + [30000] * 59
        snapshots = _make_snapshots(cfs)
        summary = _make_summary(snapshots)
        cfg = FinanceConfig(terminal_value_method="none")

        dcf = build_dcf_table(snapshots, summary, cfg, 0.10)
        assert dcf.irr is not None
        assert dcf.irr > 0
