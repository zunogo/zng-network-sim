"""Revenue & pricing — §5.6."""

from pydantic import BaseModel, Field


class RevenueConfig(BaseModel):
    """Revenue model inputs."""

    price_per_swap: float = Field(
        default=80.0, ge=0,
        description="Gross price per swap VISIT (per vehicle, not per pack). "
                    "A 2-pack vehicle pays this once per visit.",
    )
    initial_fleet_size: int = Field(default=200, ge=1, description="Vehicles at month 1")
    monthly_fleet_additions: int = Field(default=0, ge=0, description="New vehicles added each month")
