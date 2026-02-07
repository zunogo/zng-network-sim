"""Tests for engine/demand.py — stochastic demand generator.

Covers:
  - Output shape and non-negativity
  - Deterministic mode matches static engine
  - Poisson mean convergence
  - Gamma mean convergence and variance scaling
  - Weekend factor reduces weekend demand
  - Seasonal amplitude creates month-to-month variation
  - Seed reproducibility
  - Monthly convenience wrapper
  - Fleet growth scales demand linearly
"""

from __future__ import annotations

import numpy as np
import pytest

from zng_simulator.config.demand import DemandConfig
from zng_simulator.engine.demand import (
    DAYS_PER_MONTH,
    generate_daily_demand,
    generate_monthly_demand,
)
from zng_simulator.models.results import DerivedParams


# ═══════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def base_derived() -> DerivedParams:
    """Minimal DerivedParams with realistic values for demand tests."""
    return DerivedParams(
        energy_per_swap_cycle_per_pack_kwh=1.024,
        energy_per_swap_cycle_per_vehicle_kwh=2.048,
        total_energy_per_vehicle_kwh=2.56,
        daily_energy_need_wh=3000.0,
        swap_visits_per_vehicle_per_day=1.4648,
        charge_time_minutes=85.33,
        effective_c_rate=0.7813,
        cycles_per_day_per_dock=12.66,
        pack_lifetime_cycles=600,
        total_docks=40,
        cycles_per_month_per_station=3038.4,
        total_network_cycles_per_month=15192.0,
        initial_fleet_size=200,
        packs_on_vehicles=400,
        packs_in_docks=40,
        total_packs=440,
    )


# ═══════════════════════════════════════════════════════════════════════════
# Basic shape and safety
# ═══════════════════════════════════════════════════════════════════════════

class TestBasics:
    """Output shape, dtype, and non-negativity."""

    def test_shape_is_30_days(self, base_derived: DerivedParams):
        demand = DemandConfig(volatility=0.0, weekend_factor=1.0, seasonal_amplitude=0.0)
        rng = np.random.default_rng(42)
        daily = generate_daily_demand(demand, base_derived, fleet_size=200, month=1, rng=rng)
        assert daily.shape == (DAYS_PER_MONTH,)

    def test_all_values_non_negative_poisson(self, base_derived: DerivedParams):
        demand = DemandConfig(distribution="poisson")
        rng = np.random.default_rng(42)
        daily = generate_daily_demand(demand, base_derived, fleet_size=200, month=1, rng=rng)
        assert (daily >= 0).all()

    def test_all_values_non_negative_gamma(self, base_derived: DerivedParams):
        demand = DemandConfig(distribution="gamma", volatility=0.5)
        rng = np.random.default_rng(42)
        daily = generate_daily_demand(demand, base_derived, fleet_size=200, month=1, rng=rng)
        assert (daily >= 0).all()

    def test_zero_fleet_gives_zero_demand(self, base_derived: DerivedParams):
        demand = DemandConfig(distribution="poisson")
        rng = np.random.default_rng(42)
        daily = generate_daily_demand(demand, base_derived, fleet_size=0, month=1, rng=rng)
        assert daily.sum() == 0


# ═══════════════════════════════════════════════════════════════════════════
# Deterministic mode (matches Phase 1 static engine)
# ═══════════════════════════════════════════════════════════════════════════

class TestDeterministic:
    """When noise is off, demand should match the static engine exactly."""

    def test_gamma_zero_volatility_is_deterministic(self, base_derived: DerivedParams):
        """Gamma with volatility=0 → every day is the same rounded value."""
        demand = DemandConfig(
            distribution="gamma", volatility=0.0,
            weekend_factor=1.0, seasonal_amplitude=0.0,
        )
        rng = np.random.default_rng(42)
        daily = generate_daily_demand(demand, base_derived, fleet_size=200, month=1, rng=rng)
        expected = round(base_derived.swap_visits_per_vehicle_per_day * 200)
        for v in daily:
            assert int(v) == expected

    def test_deterministic_monthly_total_matches_static(self, base_derived: DerivedParams):
        """With no noise, total monthly visits ≈ static engine's visits."""
        demand = DemandConfig(
            distribution="gamma", volatility=0.0,
            weekend_factor=1.0, seasonal_amplitude=0.0,
        )
        rng = np.random.default_rng(42)
        visits, _ = generate_monthly_demand(
            demand, base_derived, fleet_size=200, month=1,
            packs_per_vehicle=2, rng=rng,
        )
        # Static engine: round(visits_per_day × fleet) × 30
        expected = round(base_derived.swap_visits_per_vehicle_per_day * 200) * 30
        assert visits == expected


# ═══════════════════════════════════════════════════════════════════════════
# Poisson distribution
# ═══════════════════════════════════════════════════════════════════════════

class TestPoisson:
    """Poisson demand: mean should converge to baseline over many samples."""

    def test_mean_converges_to_baseline(self, base_derived: DerivedParams):
        """Over 1000 months, average daily visits ≈ deterministic baseline."""
        demand = DemandConfig(
            distribution="poisson",
            weekend_factor=1.0,
            seasonal_amplitude=0.0,
        )
        rng = np.random.default_rng(42)
        expected_daily = base_derived.swap_visits_per_vehicle_per_day * 200

        totals = [
            generate_daily_demand(demand, base_derived, fleet_size=200, month=1, rng=rng).sum()
            for _ in range(1000)
        ]
        mean_monthly = np.mean(totals)
        expected_monthly = expected_daily * DAYS_PER_MONTH
        # Within 2% of expected.
        assert abs(mean_monthly - expected_monthly) / expected_monthly < 0.02

    def test_variance_equals_mean(self, base_derived: DerivedParams):
        """Poisson variance ≈ mean (per day) — fundamental property."""
        demand = DemandConfig(
            distribution="poisson",
            weekend_factor=1.0,
            seasonal_amplitude=0.0,
        )
        rng = np.random.default_rng(42)
        expected_daily = base_derived.swap_visits_per_vehicle_per_day * 200

        # Collect many single-day samples (day 0, a weekday).
        day0_samples = [
            generate_daily_demand(demand, base_derived, fleet_size=200, month=1, rng=rng)[0]
            for _ in range(5000)
        ]
        sample_var = np.var(day0_samples)
        # Poisson: var = mean.  Allow 20% tolerance for sampling noise.
        assert abs(sample_var - expected_daily) / expected_daily < 0.20


# ═══════════════════════════════════════════════════════════════════════════
# Gamma distribution
# ═══════════════════════════════════════════════════════════════════════════

class TestGamma:
    """Gamma demand: mean matches baseline, variance scales with volatility."""

    def test_mean_converges_to_baseline(self, base_derived: DerivedParams):
        demand = DemandConfig(
            distribution="gamma", volatility=0.3,
            weekend_factor=1.0, seasonal_amplitude=0.0,
        )
        rng = np.random.default_rng(42)
        expected_monthly = base_derived.swap_visits_per_vehicle_per_day * 200 * DAYS_PER_MONTH

        totals = [
            generate_daily_demand(demand, base_derived, fleet_size=200, month=1, rng=rng).sum()
            for _ in range(1000)
        ]
        assert abs(np.mean(totals) - expected_monthly) / expected_monthly < 0.02

    def test_higher_volatility_higher_variance(self, base_derived: DerivedParams):
        """Doubling volatility should increase variance significantly."""
        rng_lo = np.random.default_rng(42)
        rng_hi = np.random.default_rng(42)

        demand_lo = DemandConfig(
            distribution="gamma", volatility=0.05,
            weekend_factor=1.0, seasonal_amplitude=0.0,
        )
        demand_hi = DemandConfig(
            distribution="gamma", volatility=0.50,
            weekend_factor=1.0, seasonal_amplitude=0.0,
        )

        samples_lo = np.concatenate([
            generate_daily_demand(demand_lo, base_derived, fleet_size=200, month=1, rng=rng_lo)
            for _ in range(200)
        ])
        samples_hi = np.concatenate([
            generate_daily_demand(demand_hi, base_derived, fleet_size=200, month=1, rng=rng_hi)
            for _ in range(200)
        ])
        assert np.std(samples_hi) > np.std(samples_lo)


# ═══════════════════════════════════════════════════════════════════════════
# Weekend factor
# ═══════════════════════════════════════════════════════════════════════════

class TestWeekendFactor:
    """Weekend factor should reduce demand on Sat/Sun."""

    def test_weekend_demand_lower_than_weekday(self, base_derived: DerivedParams):
        """With weekend_factor=0.5, weekend days ≈ 50% of weekday days."""
        demand = DemandConfig(
            distribution="gamma", volatility=0.0,
            weekend_factor=0.5, seasonal_amplitude=0.0,
        )
        rng = np.random.default_rng(42)
        daily = generate_daily_demand(demand, base_derived, fleet_size=200, month=1, rng=rng)

        weekday_idx = [d for d in range(DAYS_PER_MONTH) if (d % 7) not in (5, 6)]
        weekend_idx = [d for d in range(DAYS_PER_MONTH) if (d % 7) in (5, 6)]

        weekday_mean = np.mean(daily[weekday_idx])
        weekend_mean = np.mean(daily[weekend_idx])
        assert weekend_mean < weekday_mean
        assert abs(weekend_mean / weekday_mean - 0.5) < 0.05

    def test_weekend_factor_1_no_difference(self, base_derived: DerivedParams):
        """With weekend_factor=1.0, all days should be equal."""
        demand = DemandConfig(
            distribution="gamma", volatility=0.0,
            weekend_factor=1.0, seasonal_amplitude=0.0,
        )
        rng = np.random.default_rng(42)
        daily = generate_daily_demand(demand, base_derived, fleet_size=200, month=1, rng=rng)
        assert daily.min() == daily.max()  # All identical in deterministic mode

    def test_weekend_reduces_monthly_total(self, base_derived: DerivedParams):
        """Lower weekend factor → lower monthly total."""
        demand_full = DemandConfig(
            distribution="gamma", volatility=0.0,
            weekend_factor=1.0, seasonal_amplitude=0.0,
        )
        demand_half = DemandConfig(
            distribution="gamma", volatility=0.0,
            weekend_factor=0.5, seasonal_amplitude=0.0,
        )
        rng1 = np.random.default_rng(42)
        rng2 = np.random.default_rng(42)

        total_full = generate_daily_demand(
            demand_full, base_derived, fleet_size=200, month=1, rng=rng1,
        ).sum()
        total_half = generate_daily_demand(
            demand_half, base_derived, fleet_size=200, month=1, rng=rng2,
        ).sum()
        assert total_half < total_full


# ═══════════════════════════════════════════════════════════════════════════
# Seasonal amplitude
# ═══════════════════════════════════════════════════════════════════════════

class TestSeasonalAmplitude:
    """Seasonal sinusoidal variation across months."""

    def test_peak_month_higher_than_trough(self, base_derived: DerivedParams):
        """Month 3 (sin = +1, peak) should have more demand than month 9 (trough)."""
        demand = DemandConfig(
            distribution="gamma", volatility=0.0,
            weekend_factor=1.0, seasonal_amplitude=0.2,
        )
        rng1 = np.random.default_rng(42)
        rng2 = np.random.default_rng(42)

        total_peak = generate_daily_demand(
            demand, base_derived, fleet_size=200, month=3, rng=rng1,
        ).sum()
        total_trough = generate_daily_demand(
            demand, base_derived, fleet_size=200, month=9, rng=rng2,
        ).sum()
        assert total_peak > total_trough

    def test_zero_amplitude_no_variation(self, base_derived: DerivedParams):
        """With seasonal_amplitude=0, all months are identical (deterministic mode)."""
        demand = DemandConfig(
            distribution="gamma", volatility=0.0,
            weekend_factor=1.0, seasonal_amplitude=0.0,
        )
        rng1 = np.random.default_rng(42)
        rng2 = np.random.default_rng(42)

        total_jan = generate_daily_demand(
            demand, base_derived, fleet_size=200, month=1, rng=rng1,
        ).sum()
        total_jul = generate_daily_demand(
            demand, base_derived, fleet_size=200, month=7, rng=rng2,
        ).sum()
        assert total_jan == total_jul

    def test_amplitude_magnitude(self, base_derived: DerivedParams):
        """With amplitude=0.2, peak ≈ 1.2× base and trough ≈ 0.8× base."""
        demand = DemandConfig(
            distribution="gamma", volatility=0.0,
            weekend_factor=1.0, seasonal_amplitude=0.2,
        )
        rng = np.random.default_rng(42)
        base_total = round(base_derived.swap_visits_per_vehicle_per_day * 200) * DAYS_PER_MONTH

        peak_total = generate_daily_demand(
            demand, base_derived, fleet_size=200, month=3, rng=rng,
        ).sum()
        trough_total = generate_daily_demand(
            demand, base_derived, fleet_size=200, month=9, rng=rng,
        ).sum()

        # Peak should be ~120% of base, trough ~80%.
        assert abs(peak_total / base_total - 1.2) < 0.05
        assert abs(trough_total / base_total - 0.8) < 0.05


# ═══════════════════════════════════════════════════════════════════════════
# Reproducibility
# ═══════════════════════════════════════════════════════════════════════════

class TestReproducibility:
    """Same seed → same output."""

    def test_same_seed_same_output(self, base_derived: DerivedParams):
        demand = DemandConfig(distribution="poisson")
        rng1 = np.random.default_rng(123)
        rng2 = np.random.default_rng(123)

        d1 = generate_daily_demand(demand, base_derived, fleet_size=200, month=1, rng=rng1)
        d2 = generate_daily_demand(demand, base_derived, fleet_size=200, month=1, rng=rng2)
        np.testing.assert_array_equal(d1, d2)

    def test_different_seed_different_output(self, base_derived: DerivedParams):
        demand = DemandConfig(distribution="poisson")
        rng1 = np.random.default_rng(1)
        rng2 = np.random.default_rng(999)

        d1 = generate_daily_demand(demand, base_derived, fleet_size=200, month=1, rng=rng1)
        d2 = generate_daily_demand(demand, base_derived, fleet_size=200, month=1, rng=rng2)
        # Extremely unlikely to be identical with different seeds.
        assert not np.array_equal(d1, d2)


# ═══════════════════════════════════════════════════════════════════════════
# Monthly convenience wrapper
# ═══════════════════════════════════════════════════════════════════════════

class TestMonthlyDemand:
    """generate_monthly_demand wrapper."""

    def test_returns_tuple_of_two_ints(self, base_derived: DerivedParams):
        demand = DemandConfig()
        rng = np.random.default_rng(42)
        result = generate_monthly_demand(
            demand, base_derived, fleet_size=200, month=1,
            packs_per_vehicle=2, rng=rng,
        )
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], int)
        assert isinstance(result[1], int)

    def test_cycles_equals_visits_times_packs(self, base_derived: DerivedParams):
        demand = DemandConfig()
        rng = np.random.default_rng(42)
        visits, cycles = generate_monthly_demand(
            demand, base_derived, fleet_size=200, month=1,
            packs_per_vehicle=2, rng=rng,
        )
        assert cycles == visits * 2

    def test_four_packs_per_vehicle(self, base_derived: DerivedParams):
        demand = DemandConfig()
        rng = np.random.default_rng(42)
        visits, cycles = generate_monthly_demand(
            demand, base_derived, fleet_size=200, month=1,
            packs_per_vehicle=4, rng=rng,
        )
        assert cycles == visits * 4

    def test_fleet_growth_doubles_demand(self, base_derived: DerivedParams):
        """With deterministic demand, doubling fleet exactly doubles visits."""
        demand = DemandConfig(
            distribution="gamma", volatility=0.0,
            weekend_factor=1.0, seasonal_amplitude=0.0,
        )
        rng1 = np.random.default_rng(42)
        rng2 = np.random.default_rng(42)

        visits_200, _ = generate_monthly_demand(
            demand, base_derived, fleet_size=200, month=1,
            packs_per_vehicle=2, rng=rng1,
        )
        visits_400, _ = generate_monthly_demand(
            demand, base_derived, fleet_size=400, month=1,
            packs_per_vehicle=2, rng=rng2,
        )
        assert visits_400 == 2 * visits_200
