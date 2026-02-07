"""Stochastic demand generator — Phase 2 (§7.1).

Generates daily swap-visit counts for a given month, incorporating:
  1. Deterministic baseline from ``DerivedParams.swap_visits_per_vehicle_per_day``
  2. Weekend demand reduction (``DemandConfig.weekend_factor``)
  3. Seasonal sinusoidal variation (``DemandConfig.seasonal_amplitude``)
  4. Stochastic noise — Poisson or Gamma (``DemandConfig.distribution``)

The module is pure NumPy — no side-effects, no state.  The caller passes in a
``numpy.random.Generator`` for reproducibility.

When all noise parameters are neutral (volatility=0, weekend_factor=1,
seasonal_amplitude=0) the output matches the Phase 1 static engine exactly.
"""

from __future__ import annotations

import numpy as np

from zng_simulator.config.demand import DemandConfig
from zng_simulator.models.results import DerivedParams

DAYS_PER_MONTH = 30
"""Fixed 30-day month used throughout the simulator (matches Phase 1)."""


def generate_daily_demand(
    demand: DemandConfig,
    derived: DerivedParams,
    fleet_size: int,
    month: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """Generate 30 daily swap-visit counts for one month.

    Parameters
    ----------
    demand : DemandConfig
        Stochastic demand settings (distribution, volatility, weekend, seasonal).
    derived : DerivedParams
        Operational parameters — ``swap_visits_per_vehicle_per_day`` is the key input.
    fleet_size : int
        Number of active vehicles this month.
    month : int
        1-indexed month number (1 = first month). Used for seasonal variation.
    rng : numpy.random.Generator
        Seeded RNG for reproducibility.

    Returns
    -------
    np.ndarray
        Shape ``(30,)`` of non-negative integer daily swap visits.
    """
    # ── 1. Deterministic baseline ───────────────────────────────────────
    base_daily_visits = derived.swap_visits_per_vehicle_per_day * fleet_size

    # ── 2. Seasonal adjustment ──────────────────────────────────────────
    # Sinusoidal with 12-month period.
    # month=3 → sin(π/2) = +1 (peak), month=9 → sin(3π/2) = −1 (trough)
    seasonal_factor = 1.0 + demand.seasonal_amplitude * np.sin(
        2.0 * np.pi * month / 12.0
    )

    adjusted_base = base_daily_visits * seasonal_factor

    # ── 3. Per-day means (weekday / weekend) ────────────────────────────
    daily_means = np.full(DAYS_PER_MONTH, adjusted_base, dtype=np.float64)

    # Simple weekday model: month starts on a Monday (day 0 = Mon).
    # Days 5, 6 (Sat, Sun) of each 7-day week are weekends.
    weekend_mask = np.array(
        [(d % 7) in (5, 6) for d in range(DAYS_PER_MONTH)], dtype=bool
    )
    daily_means[weekend_mask] *= demand.weekend_factor

    # ── 4. Stochastic draw ──────────────────────────────────────────────
    if demand.distribution == "poisson":
        # Poisson: variance = mean.  ``volatility`` is ignored.
        # np.maximum prevents negative λ from seasonal trough.
        daily_visits = rng.poisson(lam=np.maximum(daily_means, 0.0))

    elif demand.distribution == "gamma":
        if demand.volatility <= 0.0:
            # Zero noise → round to nearest integer (deterministic).
            daily_visits = np.round(daily_means).astype(np.int64)
        else:
            # Gamma parameterisation (mean, CoV → shape, scale):
            #   mean  = shape × scale
            #   var   = shape × scale²
            #   CoV   = σ/μ = 1/√shape  →  shape = 1/CoV²
            #   scale = mean × CoV²
            shape = 1.0 / (demand.volatility ** 2)
            scales = np.maximum(daily_means, 0.0) * (demand.volatility ** 2)
            # Guard: if any scale is ≤ 0 (possible at seasonal trough), clamp.
            scales = np.maximum(scales, 1e-10)
            daily_visits = np.round(
                rng.gamma(shape=shape, scale=scales)
            ).astype(np.int64)
    else:
        # Fallback: deterministic (should not happen with Pydantic validation).
        daily_visits = np.round(daily_means).astype(np.int64)

    # Ensure non-negative.
    return np.maximum(daily_visits, 0)


def generate_monthly_demand(
    demand: DemandConfig,
    derived: DerivedParams,
    fleet_size: int,
    month: int,
    packs_per_vehicle: int,
    rng: np.random.Generator,
) -> tuple[int, int]:
    """Generate total swap visits and cycles for one month.

    Convenience wrapper around :func:`generate_daily_demand`.

    Parameters
    ----------
    demand : DemandConfig
        Stochastic demand settings.
    derived : DerivedParams
        Operational parameters.
    fleet_size : int
        Number of active vehicles this month.
    month : int
        1-indexed month number.
    packs_per_vehicle : int
        Number of packs swapped per visit.
    rng : numpy.random.Generator
        Seeded RNG.

    Returns
    -------
    (swap_visits, total_cycles)
        - ``swap_visits``: total vehicle visits this month.
        - ``total_cycles``: swap_visits × packs_per_vehicle.
    """
    daily = generate_daily_demand(demand, derived, fleet_size, month, rng)
    swap_visits = int(daily.sum())
    total_cycles = swap_visits * packs_per_vehicle
    return swap_visits, total_cycles
