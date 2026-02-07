"""Battery pack specification — §5.2."""

from pydantic import BaseModel, Field


class PackSpec(BaseModel):
    """One battery pack variant, fixed per simulation run."""

    # --- Identity & capacity ---
    name: str = Field(default="1.28 kWh LFP", description="Human label")
    nominal_capacity_kwh: float = Field(default=1.28, gt=0, description="Nameplate energy (kWh)")
    chemistry: str = Field(default="LFP", description="Cell chemistry (NMC, LFP, etc.)")
    unit_cost: float = Field(default=18_000.0, ge=0, description="Purchase price per pack (₹)")
    weight_kg: float = Field(default=8.5, gt=0, description="Pack weight (kg)")

    # --- Degradation model ---
    cycle_life_to_retirement: int = Field(default=3_000, gt=0, description="Rated cycles to retirement SOH")
    cycle_degradation_rate_pct: float = Field(
        default=0.01, gt=0,
        description="β — SOH loss per cycle (%); e.g. 0.05 means 0.05% per cycle",
    )
    calendar_aging_rate_pct_per_month: float = Field(
        default=0.15, ge=0,
        description="SOH loss per month when idle (%)",
    )
    depth_of_discharge_pct: float = Field(default=0.95, gt=0, le=1.0, description="Typical DoD per cycle")
    retirement_soh_pct: float = Field(default=0.70, gt=0, le=1.0, description="SOH at which pack exits network")
    second_life_salvage_value: float = Field(default=6_000.0, ge=0, description="Resale value at retirement (₹)")
    aggressiveness_multiplier: float = Field(
        default=1.0, ge=0.1,
        description="Degradation multiplier for aggressive use (1.0 = normal)",
    )

    # --- Failure model (MTBF / MTTR) ---
    # Covers random / unexpected failures: BMS faults, cell swelling,
    # connector damage, physical damage during handling.
    # Separate from cycle-degradation — these are "surprise" breakdowns.
    mtbf_hours: float = Field(
        default=50_000.0, gt=0,
        description="Mean Time Between Failures (hours) — population/statistical "
                    "measure applied to the total pack fleet operating hours. "
                    "Covers BMS faults, cell failures, connector damage, etc.",
    )
    mttr_hours: float = Field(
        default=4.0, gt=0,
        description="Mean Time To Repair (hours) — diagnose + swap out the "
                    "failed pack and send for repair/reconditioning.",
    )
    repair_cost_per_event: float = Field(
        default=2_000.0, ge=0,
        description="Parts + labor per failure event (₹) — BMS reset, "
                    "cell replacement, connector repair.",
    )
    replacement_threshold: int = Field(
        default=3, ge=1,
        description="After this many repairs, the pack is fully replaced.",
    )
    full_replacement_cost: float = Field(
        default=15_000.0, ge=0,
        description="Cost to procure + deploy a replacement pack (₹).",
    )
    spare_packs_cost_per_station: float = Field(
        default=30_000.0, ge=0,
        description="Capital tied up in spare packs per station (₹).",
    )
