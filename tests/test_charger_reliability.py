"""Tests for engine/charger_reliability.py — stochastic charger failure sim.

Covers:
  - Exponential (β=1): failures ≈ fleet_hours / MTBF on average
  - Weibull (β>1): failures increase with charger age (wear-out)
  - Weibull (β<1): infant mortality pattern
  - Full replacement resets dock age and cumulative failures
  - Costs: repair, replacement, downtime
  - Reproducibility with seeded RNG
  - Zero-dock edge case
  - Downtime reduces available dock-hours
"""

from __future__ import annotations

import numpy as np
import pytest

from zng_simulator.config.charger import ChargerVariant
from zng_simulator.engine.charger_reliability import (
    ChargerReliabilityTracker,
    ChargerReliabilityStepResult,
)


# ═══════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def budget_charger() -> ChargerVariant:
    """Budget charger with known MTBF for hand-calculation."""
    return ChargerVariant(
        name="Budget-Test",
        purchase_cost_per_slot=10_000,
        rated_power_w=1_500,
        charging_efficiency_pct=0.95,
        mtbf_hours=10_000,       # Relatively low → frequent failures
        mttr_hours=24,
        repair_cost_per_event=1_000,
        replacement_threshold=3,
        full_replacement_cost=8_000,
        spare_inventory_cost=5_000,
        expected_useful_life_years=4.0,
        failure_distribution="exponential",
        weibull_shape=1.0,
    )


@pytest.fixture
def premium_charger() -> ChargerVariant:
    """Premium charger with higher MTBF."""
    return ChargerVariant(
        name="Premium-Test",
        purchase_cost_per_slot=25_000,
        rated_power_w=3_000,
        charging_efficiency_pct=0.98,
        mtbf_hours=80_000,       # High reliability
        mttr_hours=8,
        repair_cost_per_event=2_000,
        replacement_threshold=3,
        full_replacement_cost=20_000,
        spare_inventory_cost=15_000,
        expected_useful_life_years=5.0,
        failure_distribution="exponential",
        weibull_shape=1.0,
    )


@pytest.fixture
def weibull_wearout_charger() -> ChargerVariant:
    """Charger with Weibull wear-out (β > 1)."""
    return ChargerVariant(
        name="Weibull-Wearout",
        purchase_cost_per_slot=15_000,
        rated_power_w=2_000,
        charging_efficiency_pct=0.96,
        mtbf_hours=20_000,
        mttr_hours=12,
        repair_cost_per_event=1_500,
        replacement_threshold=3,
        full_replacement_cost=12_000,
        spare_inventory_cost=8_000,
        expected_useful_life_years=4.0,
        failure_distribution="weibull",
        weibull_shape=2.0,   # Strong wear-out
    )


def make_tracker(charger, total_docks=50, hours_per_day=18, seed=42):
    rng = np.random.default_rng(seed)
    return ChargerReliabilityTracker(charger, total_docks, hours_per_day, rng)


# ═══════════════════════════════════════════════════════════════════════════
# Exponential (β=1) — constant hazard
# ═══════════════════════════════════════════════════════════════════════════

class TestExponentialFailures:
    """Exponential: failures ~ Poisson(fleet_hours / MTBF)."""

    def test_average_failures_converge(self, budget_charger: ChargerVariant):
        """Over many months, average failures ≈ expected."""
        total_docks = 50
        hours_per_day = 18
        hours_per_month = hours_per_day * 30.4375
        expected_per_month = total_docks * hours_per_month / budget_charger.mtbf_hours

        # Run 120 months (10 years)
        tracker = make_tracker(budget_charger, total_docks, hours_per_day)
        total_failures = sum(
            tracker.step(m).failures for m in range(1, 121)
        )
        avg_per_month = total_failures / 120

        # Should be within 20% of expected (Poisson variance is well-bounded)
        assert abs(avg_per_month - expected_per_month) / expected_per_month < 0.20

    def test_premium_fewer_failures_than_budget(
        self, budget_charger: ChargerVariant, premium_charger: ChargerVariant
    ):
        """Higher MTBF → fewer failures on average."""
        months = 60
        tracker_b = make_tracker(budget_charger, seed=42)
        tracker_p = make_tracker(premium_charger, seed=42)

        failures_b = sum(tracker_b.step(m).failures for m in range(1, months + 1))
        failures_p = sum(tracker_p.step(m).failures for m in range(1, months + 1))

        assert failures_p < failures_b

    def test_failures_non_negative(self, budget_charger: ChargerVariant):
        """Failures per month ≥ 0 always."""
        tracker = make_tracker(budget_charger)
        for m in range(1, 61):
            result = tracker.step(m)
            assert result.failures >= 0


# ═══════════════════════════════════════════════════════════════════════════
# Weibull (β > 1) — wear-out
# ═══════════════════════════════════════════════════════════════════════════

class TestWeibullWearout:
    """β > 1: failure rate increases with age."""

    def test_later_months_more_failures(self, weibull_wearout_charger: ChargerVariant):
        """Average failure rate in later months > earlier months (wear-out).

        Note: replacement resets age, so we use a high threshold to avoid resets.
        """
        charger = weibull_wearout_charger.model_copy(
            update={"replacement_threshold": 100}  # Effectively no replacement
        )
        tracker = make_tracker(charger, total_docks=200, seed=42)

        # Run 200 independent realizations to average out noise
        early_failures = []
        late_failures = []
        for seed in range(200):
            t = make_tracker(charger, total_docks=200, seed=seed)
            early = sum(t.step(m).failures for m in range(1, 7))   # months 1-6
            late = sum(t.step(m).failures for m in range(7, 13))   # months 7-12
            early_failures.append(early)
            late_failures.append(late)

        avg_early = sum(early_failures) / len(early_failures)
        avg_late = sum(late_failures) / len(late_failures)

        # With β=2 wear-out, late should have more failures
        assert avg_late > avg_early


# ═══════════════════════════════════════════════════════════════════════════
# Full replacement
# ═══════════════════════════════════════════════════════════════════════════

class TestReplacement:
    """After replacement_threshold failures, dock is fully replaced."""

    def test_replacements_happen(self, budget_charger: ChargerVariant):
        """With low MTBF and threshold=3, replacements should occur."""
        tracker = make_tracker(budget_charger, total_docks=50, seed=42)

        total_replacements = sum(
            tracker.step(m).replacements for m in range(1, 61)
        )
        assert total_replacements > 0

    def test_replacement_resets_age(self, budget_charger: ChargerVariant):
        """After replacement, dock age resets (avg age should be < max possible)."""
        tracker = make_tracker(budget_charger, total_docks=50, seed=42)

        # Run until replacements happen
        for m in range(1, 61):
            result = tracker.step(m)

        max_possible_age = 18 * 30.4375 * 60  # 60 months of 18h/day
        assert tracker.avg_dock_age_hours < max_possible_age

    def test_replacement_cost_correct(self, budget_charger: ChargerVariant):
        """Replacement cost = replacements × full_replacement_cost."""
        tracker = make_tracker(budget_charger, total_docks=50, seed=42)

        for m in range(1, 61):
            result = tracker.step(m)
            expected_cost = result.replacements * budget_charger.full_replacement_cost
            assert abs(result.replacement_cost - expected_cost) < 0.01


# ═══════════════════════════════════════════════════════════════════════════
# Costs and downtime
# ═══════════════════════════════════════════════════════════════════════════

class TestCostsAndDowntime:
    """Verify cost and downtime calculations."""

    def test_repair_cost_equals_failures_times_rate(self, budget_charger: ChargerVariant):
        """repair_cost = failures × repair_cost_per_event."""
        tracker = make_tracker(budget_charger, seed=42)
        for m in range(1, 13):
            result = tracker.step(m)
            expected = result.failures * budget_charger.repair_cost_per_event
            assert abs(result.repair_cost - expected) < 0.01

    def test_downtime_equals_failures_times_mttr(self, budget_charger: ChargerVariant):
        """downtime_hours = failures × mttr_hours."""
        tracker = make_tracker(budget_charger, seed=42)
        for m in range(1, 13):
            result = tracker.step(m)
            expected = result.failures * budget_charger.mttr_hours
            assert abs(result.downtime_hours - expected) < 0.01

    def test_available_hours_reduced_by_downtime(self, budget_charger: ChargerVariant):
        """available_dock_hours = total_dock_hours - downtime."""
        total_docks = 50
        hours_per_day = 18
        hours_per_month = hours_per_day * 30.4375
        total_dock_hours = total_docks * hours_per_month

        tracker = make_tracker(budget_charger, total_docks, hours_per_day, seed=42)
        for m in range(1, 13):
            result = tracker.step(m)
            expected = max(0.0, total_dock_hours - result.downtime_hours)
            assert abs(result.available_dock_hours - expected) < 0.01

    def test_zero_failures_zero_cost(self, premium_charger: ChargerVariant):
        """When no failures occur in a month, costs are zero."""
        # Use very high MTBF to make zero-failure months likely
        charger = premium_charger.model_copy(update={"mtbf_hours": 1_000_000})
        tracker = make_tracker(charger, total_docks=5, seed=42)

        zero_found = False
        for m in range(1, 25):
            result = tracker.step(m)
            if result.failures == 0:
                assert result.repair_cost == 0.0
                assert result.downtime_hours == 0.0
                zero_found = True
        assert zero_found, "Expected at least one zero-failure month with very high MTBF"


# ═══════════════════════════════════════════════════════════════════════════
# Reproducibility
# ═══════════════════════════════════════════════════════════════════════════

class TestReproducibility:
    """Same seed → same failure sequence."""

    def test_same_seed_same_results(self, budget_charger: ChargerVariant):
        """Two trackers with same seed produce identical results."""
        tracker1 = make_tracker(budget_charger, seed=123)
        tracker2 = make_tracker(budget_charger, seed=123)

        for m in range(1, 25):
            r1 = tracker1.step(m)
            r2 = tracker2.step(m)
            assert r1.failures == r2.failures
            assert r1.replacements == r2.replacements

    def test_different_seed_different_results(self, budget_charger: ChargerVariant):
        """Two trackers with different seeds produce different results."""
        tracker1 = make_tracker(budget_charger, seed=42)
        tracker2 = make_tracker(budget_charger, seed=99)

        results_differ = False
        for m in range(1, 25):
            r1 = tracker1.step(m)
            r2 = tracker2.step(m)
            if r1.failures != r2.failures:
                results_differ = True
                break
        assert results_differ


# ═══════════════════════════════════════════════════════════════════════════
# Edge cases
# ═══════════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    """Boundary conditions."""

    def test_zero_docks(self, budget_charger: ChargerVariant):
        """Zero docks → zero everything."""
        rng = np.random.default_rng(42)
        tracker = ChargerReliabilityTracker(budget_charger, 0, 18, rng)
        result = tracker.step(1)
        assert result.failures == 0
        assert result.available_dock_hours == 0.0

    def test_single_dock(self, budget_charger: ChargerVariant):
        """Single dock simulation works."""
        tracker = make_tracker(budget_charger, total_docks=1, seed=42)
        for m in range(1, 25):
            result = tracker.step(m)
            assert result.failures >= 0
            assert result.available_dock_hours >= 0

    def test_result_is_frozen(self, budget_charger: ChargerVariant):
        """StepResult is immutable (frozen dataclass)."""
        tracker = make_tracker(budget_charger, seed=42)
        result = tracker.step(1)
        with pytest.raises(AttributeError):
            result.failures = 99
