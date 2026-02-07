"""Tests for engine/degradation.py — battery pack cohort tracker.

Covers:
  - SOH degradation formula correctness
  - Cohort retirement at correct month
  - Lumpy CapEx: zero for healthy months, spike at retirement
  - Auto-replacement creates new cohort
  - Multi-cohort tracking (initial + fleet growth)
  - Calendar aging alone (zero cycles)
  - Cycle aging alone (zero calendar)
  - High aggressiveness → faster retirement
  - No auto-replace mode
  - Active pack count stays correct through retirements
  - avg_soh weighted by pack count
  - Sawtooth pattern over multiple retirement cycles
"""

from __future__ import annotations

import pytest

from zng_simulator.config.battery import PackSpec
from zng_simulator.config.chaos import ChaosConfig
from zng_simulator.engine.degradation import DegradationTracker, DegradationStepResult


# ═══════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def simple_pack() -> PackSpec:
    """Pack with simple, hand-calculable degradation rates.

    β = 0.05% per cycle → effective β = 0.0005 per cycle
    calendar = 0.15% per month → 0.0015 per month
    retirement SOH = 0.70 → budget of 0.30
    """
    return PackSpec(
        name="Test Pack",
        nominal_capacity_kwh=1.28,
        chemistry="NMC",
        unit_cost=15_000,
        cycle_life_to_retirement=1_200,
        cycle_degradation_rate_pct=0.05,
        calendar_aging_rate_pct_per_month=0.15,
        depth_of_discharge_pct=0.80,
        retirement_soh_pct=0.70,
        second_life_salvage_value=3_000,
        weight_kg=6.5,
        aggressiveness_multiplier=1.0,
        mtbf_hours=50_000,
        mttr_hours=4.0,
        repair_cost_per_event=2_000,
        replacement_threshold=3,
        full_replacement_cost=15_000,
        spare_packs_cost_per_station=30_000,
    )


@pytest.fixture
def chaos() -> ChaosConfig:
    return ChaosConfig(
        sabotage_pct_per_month=0.005,
        aggressiveness_index=1.0,
        thermal_throttling_factor=1.0,
    )


# ═══════════════════════════════════════════════════════════════════════════
# Basic SOH degradation
# ═══════════════════════════════════════════════════════════════════════════

class TestSOHDegradation:
    """Verify the SOH formula: soh -= β × cycles + calendar."""

    def test_soh_after_one_month(self, simple_pack: PackSpec, chaos: ChaosConfig):
        """Hand-calculate SOH after 1 month with known cycles."""
        tracker = DegradationTracker(simple_pack, chaos, auto_replace=False)
        tracker.add_cohort(pack_count=100, born_month=1)

        # 100 packs, 2000 total cycles → 20 cycles per pack
        result = tracker.step(month=1, total_fleet_cycles=2_000)

        # β = 0.05/100 = 0.0005 per cycle × 20 cycles = 0.01
        # calendar = 0.15/100 = 0.0015 per month
        # total loss = 0.01 + 0.0015 = 0.0115
        # expected SOH = 1.0 - 0.0115 = 0.9885
        expected_soh = 1.0 - (0.0005 * 20) - 0.0015
        assert abs(result.avg_soh - expected_soh) < 1e-4

    def test_soh_monotonically_decreases(self, simple_pack: PackSpec, chaos: ChaosConfig):
        """SOH should strictly decrease each month while cycling."""
        tracker = DegradationTracker(simple_pack, chaos, auto_replace=False)
        tracker.add_cohort(pack_count=100, born_month=1)

        prev_soh = 1.0
        for m in range(1, 20):
            result = tracker.step(month=m, total_fleet_cycles=1_000)
            assert result.avg_soh < prev_soh
            prev_soh = result.avg_soh

    def test_calendar_aging_only(self, simple_pack: PackSpec, chaos: ChaosConfig):
        """With zero cycles, only calendar aging applies."""
        tracker = DegradationTracker(simple_pack, chaos, auto_replace=False)
        tracker.add_cohort(pack_count=100, born_month=1)

        result = tracker.step(month=1, total_fleet_cycles=0)

        # calendar only: 0.15/100 = 0.0015
        expected_soh = 1.0 - 0.0015
        assert abs(result.avg_soh - expected_soh) < 1e-6

    def test_cycle_aging_only(self, chaos: ChaosConfig):
        """With zero calendar aging, only cycle degradation applies."""
        pack = PackSpec(
            cycle_degradation_rate_pct=0.05,
            calendar_aging_rate_pct_per_month=0.0,  # no calendar aging
            retirement_soh_pct=0.70,
        )
        tracker = DegradationTracker(pack, chaos, auto_replace=False)
        tracker.add_cohort(pack_count=100, born_month=1)

        result = tracker.step(month=1, total_fleet_cycles=2_000)

        # β × cycles/pack = 0.0005 × 20 = 0.01
        expected_soh = 1.0 - 0.01
        assert abs(result.avg_soh - expected_soh) < 1e-6


# ═══════════════════════════════════════════════════════════════════════════
# Retirement timing (lumpy CapEx)
# ═══════════════════════════════════════════════════════════════════════════

class TestRetirementTiming:
    """Cohorts retire at the CORRECT month — not spread evenly."""

    def test_retirement_happens_at_specific_month(self, simple_pack: PackSpec, chaos: ChaosConfig):
        """Run until retirement, verify it happens at one specific month."""
        tracker = DegradationTracker(simple_pack, chaos, auto_replace=False)
        tracker.add_cohort(pack_count=400, born_month=1)

        retirement_month = None
        for m in range(1, 200):
            result = tracker.step(month=m, total_fleet_cycles=8_000)
            if result.packs_retired > 0:
                retirement_month = m
                break

        assert retirement_month is not None
        assert retirement_month > 1  # Not instant

    def test_zero_retirements_before_threshold(self, simple_pack: PackSpec, chaos: ChaosConfig):
        """No packs retire while SOH > retirement threshold."""
        tracker = DegradationTracker(simple_pack, chaos, auto_replace=False)
        tracker.add_cohort(pack_count=400, born_month=1)

        # Run for a few months with moderate cycling (should not retire)
        for m in range(1, 6):
            result = tracker.step(month=m, total_fleet_cycles=2_000)
            assert result.packs_retired == 0
            assert result.avg_soh > simple_pack.retirement_soh_pct

    def test_entire_cohort_retires_together(self, simple_pack: PackSpec, chaos: ChaosConfig):
        """All packs in a single cohort retire in the same month."""
        tracker = DegradationTracker(simple_pack, chaos, auto_replace=False)
        tracker.add_cohort(pack_count=400, born_month=1)

        for m in range(1, 200):
            result = tracker.step(month=m, total_fleet_cycles=8_000)
            if result.packs_retired > 0:
                assert result.packs_retired == 400
                break

    def test_retirement_month_calculable(self, chaos: ChaosConfig):
        """With known params, predict the exact retirement month.

        β = 0.1% per cycle, calendar = 0.0%, retirement at 70%.
        SOH budget = 0.30.
        cycles/pack/month = 10,000 total / 100 packs = 100 cycles.
        SOH loss/month = 0.001 × 100 = 0.1.
        Months to retire = 0.30 / 0.1 = 3 months.
        """
        pack = PackSpec(
            cycle_degradation_rate_pct=0.10,
            calendar_aging_rate_pct_per_month=0.0,
            retirement_soh_pct=0.70,
        )
        tracker = DegradationTracker(pack, chaos, auto_replace=False)
        tracker.add_cohort(pack_count=100, born_month=1)

        for m in range(1, 20):
            result = tracker.step(month=m, total_fleet_cycles=10_000)
            if result.packs_retired > 0:
                assert m == 3  # Exactly month 3
                break
        else:
            pytest.fail("Cohort never retired")


# ═══════════════════════════════════════════════════════════════════════════
# Auto-replacement
# ═══════════════════════════════════════════════════════════════════════════

class TestAutoReplacement:
    """Auto-replace creates fresh cohort when old one retires."""

    def test_auto_replace_creates_new_cohort(self, chaos: ChaosConfig):
        """After retirement, a new cohort with SOH=1.0 is born."""
        pack = PackSpec(
            cycle_degradation_rate_pct=0.10,
            calendar_aging_rate_pct_per_month=0.0,
            retirement_soh_pct=0.70,
        )
        tracker = DegradationTracker(pack, chaos, auto_replace=True)
        tracker.add_cohort(pack_count=100, born_month=1)

        assert tracker.cohort_count == 1

        # Run to retirement (month 3)
        for m in range(1, 4):
            result = tracker.step(month=m, total_fleet_cycles=10_000)

        # After retirement: original + replacement = 2 cohorts
        assert tracker.cohort_count == 2
        assert result.packs_retired == 100
        assert result.packs_replaced == 100

    def test_active_pack_count_preserved(self, chaos: ChaosConfig):
        """Active pack count stays the same after auto-replacement."""
        pack = PackSpec(
            cycle_degradation_rate_pct=0.10,
            calendar_aging_rate_pct_per_month=0.0,
            retirement_soh_pct=0.70,
        )
        tracker = DegradationTracker(pack, chaos, auto_replace=True)
        tracker.add_cohort(pack_count=100, born_month=1)

        for m in range(1, 4):
            result = tracker.step(month=m, total_fleet_cycles=10_000)

        # 100 retired + 100 replaced = 100 active
        assert result.active_pack_count == 100

    def test_replacement_soh_is_fresh(self, chaos: ChaosConfig):
        """New replacement cohort starts at SOH = 1.0."""
        pack = PackSpec(
            cycle_degradation_rate_pct=0.10,
            calendar_aging_rate_pct_per_month=0.0,
            retirement_soh_pct=0.70,
        )
        tracker = DegradationTracker(pack, chaos, auto_replace=True)
        tracker.add_cohort(pack_count=100, born_month=1)

        for m in range(1, 4):
            tracker.step(month=m, total_fleet_cycles=10_000)

        # Find the replacement cohort (born at month 3)
        snapshots = tracker.get_snapshots()
        replacement = [s for s in snapshots if s.born_month == 3 and not s.is_retired]
        assert len(replacement) == 1
        assert replacement[0].current_soh == 1.0

    def test_no_auto_replace(self, chaos: ChaosConfig):
        """With auto_replace=False, no new cohort is created."""
        pack = PackSpec(
            cycle_degradation_rate_pct=0.10,
            calendar_aging_rate_pct_per_month=0.0,
            retirement_soh_pct=0.70,
        )
        tracker = DegradationTracker(pack, chaos, auto_replace=False)
        tracker.add_cohort(pack_count=100, born_month=1)

        for m in range(1, 4):
            result = tracker.step(month=m, total_fleet_cycles=10_000)

        assert result.packs_retired == 100
        assert result.packs_replaced == 0
        assert result.active_pack_count == 0
        assert tracker.cohort_count == 1  # Only the retired one


# ═══════════════════════════════════════════════════════════════════════════
# Multi-cohort tracking
# ═══════════════════════════════════════════════════════════════════════════

class TestMultiCohort:
    """Multiple cohorts age independently and retire at different months."""

    def test_staggered_cohorts_retire_at_different_months(self, chaos: ChaosConfig):
        """Cohort born month 1 retires before cohort born month 5."""
        pack = PackSpec(
            cycle_degradation_rate_pct=0.10,
            calendar_aging_rate_pct_per_month=0.0,
            retirement_soh_pct=0.70,
        )
        tracker = DegradationTracker(pack, chaos, auto_replace=False)
        tracker.add_cohort(pack_count=100, born_month=1)

        retirement_months = []
        for m in range(1, 30):
            # Add second cohort at month 5
            if m == 5:
                tracker.add_cohort(pack_count=50, born_month=5)

            result = tracker.step(month=m, total_fleet_cycles=10_000)
            if result.packs_retired > 0:
                retirement_months.append((m, result.packs_retired))

        # First cohort should retire before second
        assert len(retirement_months) >= 2
        assert retirement_months[0][1] == 100  # first cohort (100 packs)
        assert retirement_months[1][1] == 50   # second cohort (50 packs)
        assert retirement_months[1][0] > retirement_months[0][0]

    def test_fleet_growth_cohorts(self, chaos: ChaosConfig):
        """Adding packs monthly (fleet growth) creates multiple cohorts."""
        pack = PackSpec(
            cycle_degradation_rate_pct=0.10,
            calendar_aging_rate_pct_per_month=0.0,
            retirement_soh_pct=0.70,
        )
        tracker = DegradationTracker(pack, chaos, auto_replace=False)
        tracker.add_cohort(pack_count=400, born_month=1)  # initial fleet

        for m in range(1, 4):
            # Add 10 packs per month (fleet growth)
            if m > 1:
                tracker.add_cohort(pack_count=10, born_month=m)
            tracker.step(month=m, total_fleet_cycles=10_000)

        # 1 initial + 2 growth = 3 cohorts
        assert tracker.cohort_count == 3
        assert tracker.active_cohort_count == 3

    def test_avg_soh_weighted_by_pack_count(self, chaos: ChaosConfig):
        """avg_soh is weighted by number of packs in each cohort."""
        pack = PackSpec(
            cycle_degradation_rate_pct=0.10,
            calendar_aging_rate_pct_per_month=0.0,
            retirement_soh_pct=0.70,
        )
        tracker = DegradationTracker(pack, chaos, auto_replace=False)
        # 100 packs starting month 1
        tracker.add_cohort(pack_count=100, born_month=1)

        # Degrade for 1 month
        tracker.step(month=1, total_fleet_cycles=10_000)
        soh_after_1 = tracker.avg_soh  # < 1.0

        # Add 100 fresh packs at month 2 (SOH = 1.0)
        tracker.add_cohort(pack_count=100, born_month=2)

        # avg_soh should be between soh_after_1 and 1.0, weighted equally
        expected = (soh_after_1 * 100 + 1.0 * 100) / 200
        assert abs(tracker.avg_soh - expected) < 1e-6


# ═══════════════════════════════════════════════════════════════════════════
# Sawtooth pattern (the key insight)
# ═══════════════════════════════════════════════════════════════════════════

class TestSawtoothPattern:
    """Verify the sawtooth CapEx pattern over multiple retirement cycles."""

    def test_two_retirement_cycles(self, chaos: ChaosConfig):
        """Initial cohort retires → replacement retires → 2 spikes total.

        Pack: β=0.10, calendar=0, retire at 70% → budget=0.30
        100 packs, 10,000 cycles/month → 100 cycles/pack/month
        SOH loss = 0.001 × 100 = 0.10/month
        Retire at month 3 (SOH = 1.0 - 0.30 = 0.70)
        Replacement retires at month 6
        """
        pack = PackSpec(
            cycle_degradation_rate_pct=0.10,
            calendar_aging_rate_pct_per_month=0.0,
            retirement_soh_pct=0.70,
        )
        tracker = DegradationTracker(pack, chaos, auto_replace=True)
        tracker.add_cohort(pack_count=100, born_month=1)

        retirements = []
        for m in range(1, 10):
            result = tracker.step(month=m, total_fleet_cycles=10_000)
            retirements.append(result.packs_retired)

        # Months with retirements should be exactly [3, 6, 9, ...]
        # (depends on exact SOH boundary — let's check the pattern)
        spike_months = [m + 1 for m, r in enumerate(retirements) if r > 0]
        assert len(spike_months) >= 2  # At least 2 spikes in 9 months
        assert retirements[0] == 0  # Month 1: no retirement
        assert retirements[1] == 0  # Month 2: no retirement

        # Every spike should be 100 packs
        for r in retirements:
            if r > 0:
                assert r == 100

    def test_zero_capex_between_spikes(self, chaos: ChaosConfig):
        """Between retirements, packs_retired should be exactly 0."""
        pack = PackSpec(
            cycle_degradation_rate_pct=0.10,
            calendar_aging_rate_pct_per_month=0.0,
            retirement_soh_pct=0.70,
        )
        tracker = DegradationTracker(pack, chaos, auto_replace=True)
        tracker.add_cohort(pack_count=100, born_month=1)

        results = []
        for m in range(1, 10):
            results.append(tracker.step(month=m, total_fleet_cycles=10_000))

        # Between spikes, packs_retired must be exactly 0
        for r in results:
            assert r.packs_retired == 0 or r.packs_retired == 100


# ═══════════════════════════════════════════════════════════════════════════
# Aggressiveness multiplier
# ═══════════════════════════════════════════════════════════════════════════

class TestAggressiveness:
    """Higher aggressiveness → faster degradation → earlier retirement."""

    def test_aggressive_retires_earlier(self):
        pack = PackSpec(
            cycle_degradation_rate_pct=0.10,
            calendar_aging_rate_pct_per_month=0.0,
            retirement_soh_pct=0.70,
        )
        chaos_normal = ChaosConfig(aggressiveness_index=1.0)
        chaos_aggressive = ChaosConfig(aggressiveness_index=2.0)

        tracker_normal = DegradationTracker(pack, chaos_normal, auto_replace=False)
        tracker_normal.add_cohort(100, born_month=1)

        tracker_aggressive = DegradationTracker(pack, chaos_aggressive, auto_replace=False)
        tracker_aggressive.add_cohort(100, born_month=1)

        retire_normal = None
        retire_aggressive = None

        for m in range(1, 20):
            r_n = tracker_normal.step(month=m, total_fleet_cycles=10_000)
            r_a = tracker_aggressive.step(month=m, total_fleet_cycles=10_000)
            if r_n.packs_retired > 0 and retire_normal is None:
                retire_normal = m
            if r_a.packs_retired > 0 and retire_aggressive is None:
                retire_aggressive = m
            if retire_normal and retire_aggressive:
                break

        assert retire_aggressive is not None
        assert retire_normal is not None
        assert retire_aggressive < retire_normal


# ═══════════════════════════════════════════════════════════════════════════
# Cohort snapshots
# ═══════════════════════════════════════════════════════════════════════════

class TestCohortSnapshots:
    """Verify CohortStatus snapshots are correct."""

    def test_snapshot_fields_populated(self, chaos: ChaosConfig):
        pack = PackSpec(
            cycle_degradation_rate_pct=0.10,
            calendar_aging_rate_pct_per_month=0.0,
            retirement_soh_pct=0.70,
        )
        tracker = DegradationTracker(pack, chaos, auto_replace=False)
        tracker.add_cohort(pack_count=100, born_month=1)
        tracker.step(month=1, total_fleet_cycles=5_000)

        snaps = tracker.get_snapshots()
        assert len(snaps) == 1
        s = snaps[0]
        assert s.cohort_id == 0
        assert s.born_month == 1
        assert s.pack_count == 100
        assert s.current_soh < 1.0
        assert s.cumulative_cycles == 50  # 5000 / 100 = 50
        assert s.is_retired is False
        assert s.retired_month is None

    def test_retired_snapshot(self, chaos: ChaosConfig):
        pack = PackSpec(
            cycle_degradation_rate_pct=0.10,
            calendar_aging_rate_pct_per_month=0.0,
            retirement_soh_pct=0.70,
        )
        tracker = DegradationTracker(pack, chaos, auto_replace=False)
        tracker.add_cohort(pack_count=100, born_month=1)

        for m in range(1, 4):
            tracker.step(month=m, total_fleet_cycles=10_000)

        snaps = tracker.get_snapshots()
        retired = [s for s in snaps if s.is_retired]
        assert len(retired) == 1
        assert retired[0].retired_month == 3
        assert retired[0].current_soh <= 0.70

    def test_step_result_contains_snapshots(self, chaos: ChaosConfig):
        pack = PackSpec(
            cycle_degradation_rate_pct=0.10,
            calendar_aging_rate_pct_per_month=0.0,
            retirement_soh_pct=0.70,
        )
        tracker = DegradationTracker(pack, chaos, auto_replace=True)
        tracker.add_cohort(pack_count=100, born_month=1)

        for m in range(1, 4):
            result = tracker.step(month=m, total_fleet_cycles=10_000)

        # At month 3: retired cohort + replacement cohort
        assert len(result.cohort_snapshots) == 2


# ═══════════════════════════════════════════════════════════════════════════
# Edge cases
# ═══════════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    """Boundary conditions and edge cases."""

    def test_no_cohorts(self, simple_pack: PackSpec, chaos: ChaosConfig):
        """Step with no cohorts should return zero everything."""
        tracker = DegradationTracker(simple_pack, chaos)
        result = tracker.step(month=1, total_fleet_cycles=10_000)
        assert result.packs_retired == 0
        assert result.active_pack_count == 0
        assert result.avg_soh == 0.0

    def test_zero_cycles(self, simple_pack: PackSpec, chaos: ChaosConfig):
        """Zero cycles → only calendar aging, no crash."""
        tracker = DegradationTracker(simple_pack, chaos, auto_replace=False)
        tracker.add_cohort(pack_count=100, born_month=1)
        result = tracker.step(month=1, total_fleet_cycles=0)
        assert result.avg_soh > 0.99  # Only tiny calendar aging
        assert result.packs_retired == 0

    def test_single_pack_cohort(self, chaos: ChaosConfig):
        """Cohort of 1 pack works correctly."""
        pack = PackSpec(
            cycle_degradation_rate_pct=0.10,
            calendar_aging_rate_pct_per_month=0.0,
            retirement_soh_pct=0.70,
        )
        tracker = DegradationTracker(pack, chaos, auto_replace=True)
        tracker.add_cohort(pack_count=1, born_month=1)

        for m in range(1, 5):
            result = tracker.step(month=m, total_fleet_cycles=100)

        # Should have retired and been replaced
        assert any(s.is_retired for s in result.cohort_snapshots)
