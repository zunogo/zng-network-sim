"""Battery degradation cohort tracker — Phase 2 (§7.2).

Tracks **cohorts** of battery packs through their lifecycle:
  1. SOH degrades each month from cycling + calendar aging
  2. When SOH ≤ retirement threshold → cohort retires → lumpy CapEx event
  3. Replacement cohort is born (SOH = 1.0) and starts cycling next month

This is what fixes the Phase 1 lie of evenly-spread replacement costs.
In reality:

  Month 1-29:  replacement_capex = ₹0          ← packs are healthy
  Month 30:    replacement_capex = ₹72,00,000   ← entire initial cohort retires!
  Month 31-59: replacement_capex = ₹0          ← replacement cohort is healthy
  Month 60:    replacement_capex = ₹72,00,000   ← replacement cohort retires

The sawtooth CapEx pattern is the *real* cashflow investors need to plan around.

SOH model (per pack, per month):
  soh_loss_cycling  = (β / 100) × aggressiveness × cycles_per_pack_this_month
  soh_loss_calendar = calendar_aging_rate_pct / 100
  new_soh           = old_soh − soh_loss_cycling − soh_loss_calendar
  retire if          new_soh ≤ retirement_soh_pct
"""

from __future__ import annotations

from dataclasses import dataclass, field

from zng_simulator.config.battery import PackSpec
from zng_simulator.config.chaos import ChaosConfig
from zng_simulator.models.results import CohortStatus


# ═══════════════════════════════════════════════════════════════════════════
# Internal mutable cohort (lightweight dataclass for simulation speed)
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class _Cohort:
    """Mutable internal state for one pack cohort."""

    cohort_id: int
    born_month: int
    pack_count: int
    current_soh: float = 1.0
    cumulative_cycles: int = 0
    is_retired: bool = False
    retired_month: int | None = None

    def to_snapshot(self) -> CohortStatus:
        """Convert to immutable Pydantic model for output."""
        return CohortStatus(
            cohort_id=self.cohort_id,
            born_month=self.born_month,
            pack_count=self.pack_count,
            current_soh=round(self.current_soh, 6),
            cumulative_cycles=self.cumulative_cycles,
            is_retired=self.is_retired,
            retired_month=self.retired_month,
        )


# ═══════════════════════════════════════════════════════════════════════════
# Step result
# ═══════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class DegradationStepResult:
    """Immutable output of one month's degradation step.

    The orchestrator uses ``packs_retired`` and ``packs_replaced`` to compute
    the lumpy CapEx for this month:
      replacement_capex = packs_retired × pack.unit_cost
      salvage_credit    = packs_retired × pack.second_life_salvage_value
      net_cost          = replacement_capex − salvage_credit
    """

    packs_retired: int
    """Total packs that hit retirement threshold this month."""

    packs_replaced: int
    """New packs added to replace retired ones (= packs_retired when auto_replace=True)."""

    active_pack_count: int
    """Total active (non-retired) packs after this step."""

    avg_soh: float
    """Weighted average SOH across all active packs (0–1). 0.0 if no active packs."""

    cohort_snapshots: list[CohortStatus] = field(default_factory=list)
    """Snapshot of every cohort (active + retired) at the end of this month."""


# ═══════════════════════════════════════════════════════════════════════════
# Degradation tracker
# ═══════════════════════════════════════════════════════════════════════════

class DegradationTracker:
    """Manages pack cohorts and steps them through monthly degradation.

    Usage::

        tracker = DegradationTracker(pack_spec, chaos_config)
        tracker.add_cohort(pack_count=400, born_month=1)  # initial fleet
        tracker.add_cohort(pack_count=40, born_month=1)   # dock packs

        for month in range(1, 61):
            result = tracker.step(month, total_fleet_cycles=17_000)
            # result.packs_retired → lumpy CapEx for this month
            # result.avg_soh → fleet health indicator

    Parameters
    ----------
    pack : PackSpec
        Battery pack specification (degradation rates, retirement threshold).
    chaos : ChaosConfig | None
        Optional chaos config (aggressiveness index).
    auto_replace : bool
        If True, retired packs are automatically replaced with fresh cohorts
        (same pack count, SOH = 1.0) in the same month.
    """

    def __init__(
        self,
        pack: PackSpec,
        chaos: ChaosConfig | None = None,
        auto_replace: bool = True,
    ) -> None:
        self._pack = pack
        self._aggressiveness = chaos.aggressiveness_index if chaos else 1.0
        self._auto_replace = auto_replace

        # Effective β per cycle (fraction, not %)
        self._beta_per_cycle = (pack.cycle_degradation_rate_pct / 100.0) * self._aggressiveness

        # Calendar aging per month (fraction, not %)
        self._calendar_per_month = pack.calendar_aging_rate_pct_per_month / 100.0

        # Retirement threshold
        self._retirement_soh = pack.retirement_soh_pct

        # Cohort storage
        self._cohorts: list[_Cohort] = []
        self._next_id: int = 0

    # ── Public API ──────────────────────────────────────────────────────

    def add_cohort(self, pack_count: int, born_month: int) -> int:
        """Add a new cohort of packs. Returns the assigned cohort_id."""
        cid = self._next_id
        self._next_id += 1
        self._cohorts.append(_Cohort(
            cohort_id=cid,
            born_month=born_month,
            pack_count=pack_count,
        ))
        return cid

    @property
    def active_pack_count(self) -> int:
        """Total packs across all non-retired cohorts."""
        return sum(c.pack_count for c in self._cohorts if not c.is_retired)

    @property
    def avg_soh(self) -> float:
        """Pack-count-weighted average SOH of active cohorts."""
        total_packs = 0
        weighted_soh = 0.0
        for c in self._cohorts:
            if not c.is_retired:
                total_packs += c.pack_count
                weighted_soh += c.current_soh * c.pack_count
        return weighted_soh / total_packs if total_packs > 0 else 0.0

    @property
    def cohort_count(self) -> int:
        """Total cohorts (including retired)."""
        return len(self._cohorts)

    @property
    def active_cohort_count(self) -> int:
        """Number of non-retired cohorts."""
        return sum(1 for c in self._cohorts if not c.is_retired)

    def get_snapshots(self) -> list[CohortStatus]:
        """Current state of all cohorts (active + retired)."""
        return [c.to_snapshot() for c in self._cohorts]

    def step(self, month: int, total_fleet_cycles: int) -> DegradationStepResult:
        """Advance one month: degrade SOH, check retirements, auto-replace.

        Parameters
        ----------
        month : int
            1-indexed current month.
        total_fleet_cycles : int
            Total charge-discharge cycles across the entire fleet this month.
            Distributed uniformly across all active packs.

        Returns
        -------
        DegradationStepResult
            Retirements, replacements, avg SOH, and cohort snapshots.
        """
        active_packs = self.active_pack_count
        if active_packs <= 0:
            return DegradationStepResult(
                packs_retired=0,
                packs_replaced=0,
                active_pack_count=0,
                avg_soh=0.0,
                cohort_snapshots=self.get_snapshots(),
            )

        # ── 1. Allocate cycles uniformly across active packs ────────────
        cycles_per_pack = total_fleet_cycles / active_packs

        # ── 2. Degrade each active cohort ───────────────────────────────
        soh_loss_cycling = self._beta_per_cycle * cycles_per_pack
        soh_loss_calendar = self._calendar_per_month
        total_soh_loss = soh_loss_cycling + soh_loss_calendar

        packs_retired_this_month = 0
        newly_retired: list[_Cohort] = []

        for cohort in self._cohorts:
            if cohort.is_retired:
                continue

            # Apply degradation
            cohort.current_soh -= total_soh_loss
            cohort.cumulative_cycles += int(round(cycles_per_pack))

            # Check retirement (epsilon handles IEEE-754 float noise:
            # e.g. 1.0 − 0.1 − 0.1 − 0.1 = 0.7000000000000001, not 0.7)
            if cohort.current_soh <= self._retirement_soh + 1e-9:
                cohort.is_retired = True
                cohort.retired_month = month
                packs_retired_this_month += cohort.pack_count
                newly_retired.append(cohort)

        # ── 3. Auto-replace retired cohorts ─────────────────────────────
        packs_replaced = 0
        if self._auto_replace and packs_retired_this_month > 0:
            for retired_cohort in newly_retired:
                self.add_cohort(
                    pack_count=retired_cohort.pack_count,
                    born_month=month,
                )
                packs_replaced += retired_cohort.pack_count

        # ── 4. Build result ─────────────────────────────────────────────
        return DegradationStepResult(
            packs_retired=packs_retired_this_month,
            packs_replaced=packs_replaced,
            active_pack_count=self.active_pack_count,
            avg_soh=round(self.avg_soh, 6),
            cohort_snapshots=self.get_snapshots(),
        )
