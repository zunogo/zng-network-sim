"""Chaos & indirect variables — §5.7."""

from pydantic import BaseModel, Field


class ChaosConfig(BaseModel):
    """Stochastic / risk inputs."""

    sabotage_pct_per_month: float = Field(
        default=0.005, ge=0, le=1.0,
        description="Monthly rate of pack loss (theft/vandalism), e.g. 0.005 = 0.5%",
    )
    aggressiveness_index: float = Field(default=1.0, ge=0.1, description="Driver behavior multiplier on degradation")
    thermal_throttling_factor: float = Field(
        default=1.0, ge=0.1, le=2.0,
        description="Charging power de-rating (1.0 = no throttling)",
    )
