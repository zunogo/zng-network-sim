"""Charger reliability — stochastic month-by-month failure simulation (§7.3).

This complements the *deterministic* ``charger_tco.py`` (Phase 1) with a
stochastic per-dock simulation that respects the configured failure distribution.

Exponential (β = 1):
  Constant hazard rate λ = 1 / MTBF.
  Each month, expected failures per dock = operating_hours / MTBF.
  This is identical to the Phase 1 fleet-level formula, but sampled stochastically.

Weibull (β ≠ 1):
  Time-varying hazard h(t) = (β / η) × (t / η)^(β − 1).
  β < 1 → infant mortality (burn-in failures, decreasing rate).
  β > 1 → wear-out (failures increase with age).
  Each dock's age is tracked independently so the hazard is computed correctly.

The Weibull scale η is derived from MTBF:
  η = MTBF / Γ(1 + 1/β)

Per-dock failures are sampled from Poisson(ΔH) where ΔH is the
incremental cumulative hazard over the month:
  ΔH = (t_end / η)^β − (t_start / η)^β

After ``replacement_threshold`` cumulative failures, a dock's charger is
fully replaced (age resets to 0, cumulative failures reset).
"""

from __future__ import annotations

from dataclasses import dataclass
from math import gamma as math_gamma

import numpy as np

from zng_simulator.config.charger import ChargerVariant


# ═══════════════════════════════════════════════════════════════════════════
# Step result
# ═══════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class ChargerReliabilityStepResult:
    """Immutable output of one month's charger reliability step."""

    failures: int
    """Total charger failures across the fleet this month."""

    replacements: int
    """Full replacements triggered (cumulative failures hit threshold)."""

    repair_cost: float
    """failures × repair_cost_per_event (₹)."""

    replacement_cost: float
    """replacements × full_replacement_cost (₹)."""

    downtime_hours: float
    """failures × mttr_hours — fleet-wide hours of dock unavailability."""

    available_dock_hours: float
    """total_dock_hours − downtime_hours (clamped ≥ 0)."""


# ═══════════════════════════════════════════════════════════════════════════
# Reliability tracker
# ═══════════════════════════════════════════════════════════════════════════

class ChargerReliabilityTracker:
    """Tracks per-dock charger age and simulates failures stochastically.

    Usage::

        tracker = ChargerReliabilityTracker(charger, total_docks=50,
                                             operating_hours_per_day=18,
                                             rng=np.random.default_rng(42))
        for month in range(1, 61):
            result = tracker.step(month)
            # result.failures → charger_failures for MonthlySnapshot
            # result.available_dock_hours → reduce capacity for demand matching
            # result.repair_cost + result.replacement_cost → OpEx/CapEx

    Parameters
    ----------
    charger : ChargerVariant
        Charger spec (MTBF, MTTR, failure_distribution, weibull_shape, costs).
    total_docks : int
        Number of charger docks in the network (stations × docks_per_station).
    operating_hours_per_day : float
        Station operating hours per day (e.g., 18h).
    rng : np.random.Generator
        Seeded random number generator for reproducibility.
    """

    # Average days per month (365.25 / 12)
    _DAYS_PER_MONTH = 30.4375

    def __init__(
        self,
        charger: ChargerVariant,
        total_docks: int,
        operating_hours_per_day: float,
        rng: np.random.Generator,
    ) -> None:
        self._charger = charger
        self._total_docks = total_docks
        self._hours_per_month = operating_hours_per_day * self._DAYS_PER_MONTH
        self._rng = rng

        # Weibull parameters
        self._beta = charger.weibull_shape  # shape
        self._eta = charger.mtbf_hours / math_gamma(1 + 1 / self._beta)  # scale

        # Per-dock arrays
        self._age_hours = np.zeros(total_docks, dtype=np.float64)
        self._cumulative_failures = np.zeros(total_docks, dtype=np.int64)

    # ── Public API ──────────────────────────────────────────────────────

    @property
    def total_docks(self) -> int:
        return self._total_docks

    @property
    def avg_dock_age_hours(self) -> float:
        """Average charger age across all docks (hours)."""
        return float(self._age_hours.mean()) if self._total_docks > 0 else 0.0

    def step(self, month: int) -> ChargerReliabilityStepResult:
        """Simulate one month of charger operation.

        Parameters
        ----------
        month : int
            1-indexed current month (for logging; not used in computation).

        Returns
        -------
        ChargerReliabilityStepResult
        """
        if self._total_docks <= 0:
            return ChargerReliabilityStepResult(
                failures=0, replacements=0,
                repair_cost=0.0, replacement_cost=0.0,
                downtime_hours=0.0, available_dock_hours=0.0,
            )

        h = self._hours_per_month
        β = self._beta
        η = self._eta

        # ── 1. Compute incremental cumulative hazard per dock ───────────
        t_start = self._age_hours
        t_end = t_start + h

        # ΔH = (t_end / η)^β − (t_start / η)^β
        h_start = (t_start / η) ** β
        h_end = (t_end / η) ** β
        delta_h = h_end - h_start  # expected failures per dock this month

        # ── 2. Sample failures from Poisson ─────────────────────────────
        # Clamp delta_h to avoid numerical issues with very large values
        delta_h = np.clip(delta_h, 0.0, 100.0)
        failures_per_dock = self._rng.poisson(delta_h)

        total_failures = int(failures_per_dock.sum())

        # ── 3. Update cumulative failures ───────────────────────────────
        self._cumulative_failures += failures_per_dock

        # ── 4. Check full replacements ──────────────────────────────────
        needs_replacement = self._cumulative_failures >= self._charger.replacement_threshold
        num_replacements = int(needs_replacement.sum())

        # Reset replaced docks (new charger: age = 0, failures = 0)
        self._age_hours[needs_replacement] = 0.0
        self._cumulative_failures[needs_replacement] = 0

        # ── 5. Age non-replaced docks ───────────────────────────────────
        self._age_hours[~needs_replacement] += h

        # ── 6. Compute costs ────────────────────────────────────────────
        repair_cost = total_failures * self._charger.repair_cost_per_event
        replacement_cost = num_replacements * self._charger.full_replacement_cost
        downtime_hours = total_failures * self._charger.mttr_hours

        total_dock_hours = self._total_docks * h
        available_dock_hours = max(0.0, total_dock_hours - downtime_hours)

        return ChargerReliabilityStepResult(
            failures=total_failures,
            replacements=num_replacements,
            repair_cost=round(repair_cost, 2),
            replacement_cost=round(replacement_cost, 2),
            downtime_hours=round(downtime_hours, 2),
            available_dock_hours=round(available_dock_hours, 2),
        )
