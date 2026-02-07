"""Vehicle configuration — §5.1."""

from pydantic import BaseModel, Field


class VehicleConfig(BaseModel):
    """One vehicle configuration, fixed per simulation run."""

    name: str = Field(default="Heavy 2W", description="Human label for this vehicle type")
    packs_per_vehicle: int = Field(default=2, ge=1, le=4, description="Number of swappable packs carried")
    pack_capacity_kwh: float = Field(default=1.28, gt=0, description="Capacity of each pack (kWh)")
    avg_daily_km: float = Field(default=150.0, gt=0, description="Expected daily distance traveled (km)")
    energy_consumption_wh_per_km: float = Field(default=30.0, gt=0, description="Vehicle efficiency (Wh/km)")
    swap_time_minutes: float = Field(default=0.5, gt=0, description="Time for one pack swap (minutes)")
    range_anxiety_buffer_pct: float = Field(
        default=0.20, ge=0, le=1.0,
        description="Driver-behaviour SoC at which they swap (e.g. 0.20 = swap at 20% SoC). "
                    "Not a hard limit — a behavioural assumption.",
    )
