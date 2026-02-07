"""Charger variant — §5.3.  Multiple allowed per scenario for comparison."""

from typing import Literal

from pydantic import BaseModel, Field


class ChargerVariant(BaseModel):
    """One charger option.  The simulator compares across variants."""

    name: str = Field(default="Budget-1kW", description="Human label")
    purchase_cost_per_slot: float = Field(default=15_000.0, ge=0, description="Unit CapEx per slot (₹)")
    rated_power_w: float = Field(default=1_500.0, gt=0, description="Charging power per slot (W)")
    charging_efficiency_pct: float = Field(default=0.97, gt=0, le=1.0, description="Wall-to-pack efficiency")
    efficiency_decay_pct_per_year: float = Field(
        default=0.005, ge=0,
        description="Annual efficiency loss fraction (e.g. 0.005 = 0.5%/yr)",
    )
    mtbf_hours: float = Field(
        default=80_000.0, gt=0,
        description="Mean Time Between Failures (hours) — a population/statistical "
                    "measure.  Applied to the total fleet operating hours, not per dock. "
                    "Expected fleet failures = (hrs/day × 365 × years × total_docks) / MTBF.",
    )
    mttr_hours: float = Field(default=24.0, gt=0, description="Mean time to repair (hours)")
    repair_cost_per_event: float = Field(default=1_000.0, ge=0, description="Parts + labor per failure (₹)")
    replacement_threshold: int = Field(default=3, ge=1, description="Replace unit after N repairs")
    full_replacement_cost: float = Field(default=9_500.0, ge=0, description="Cost of full unit swap (₹)")
    spare_inventory_cost: float = Field(default=10_000.0, ge=0, description="Capital tied up in spares (₹)")
    expected_useful_life_years: float = Field(default=4.0, gt=0, description="Calendar life (years)")

    # --- Phase 2: stochastic failure model ---
    failure_distribution: Literal["exponential", "weibull"] = Field(
        default="exponential",
        description="Failure time distribution for stochastic simulation. "
                    "'exponential' = constant hazard rate (memoryless, standard MTBF). "
                    "'weibull' = shape-dependent hazard (β<1: infant mortality, "
                    "β=1: exponential, β>1: wear-out).",
    )
    weibull_shape: float = Field(
        default=1.0,
        gt=0,
        description="Weibull shape parameter (β). Only used when "
                    "failure_distribution='weibull'. "
                    "β=1.0 → exponential (constant hazard). "
                    "β=1.5 → mild wear-out. β=2.0 → strong wear-out. "
                    "β=0.5 → infant mortality.",
    )
