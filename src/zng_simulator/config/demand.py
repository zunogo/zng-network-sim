"""Stochastic demand configuration — Phase 2 (§5.8).

Controls how daily swap demand is generated in the stochastic engine.
Ignored by Phase 1's static engine.
"""

from typing import Literal

from pydantic import BaseModel, Field


class DemandConfig(BaseModel):
    """Stochastic demand model settings.

    Phase 1 (static engine) ignores this entirely — demand is deterministic
    from ``avg_daily_km``, ``energy_consumption_wh_per_km``, and fleet size.

    Phase 2 introduces daily demand noise:
    - **poisson**: Each vehicle's daily swap visits ~ Poisson(λ = deterministic visits/day).
      Simple, integer-valued, variance = mean.
    - **gamma**: Daily visits ~ Gamma(shape, scale) parameterised so that
      mean = deterministic visits/day and CoV = ``volatility``.
      Allows heavier tails and non-integer demand.
    """

    distribution: Literal["poisson", "gamma"] = Field(
        default="poisson",
        description="Demand distribution: 'poisson' (variance = mean) "
                    "or 'gamma' (heavier tails, configurable CoV).",
    )
    volatility: float = Field(
        default=0.15,
        ge=0.0,
        le=2.0,
        description="Coefficient of variation (σ/μ) for the Gamma distribution. "
                    "Ignored when distribution='poisson'. "
                    "0.0 = deterministic, 0.15 = mild noise, 0.5 = high variability.",
    )
    weekend_factor: float = Field(
        default=0.6,
        ge=0.0,
        le=2.0,
        description="Multiplicative factor applied to weekend demand. "
                    "1.0 = same as weekday, 0.6 = 40% drop on weekends.",
    )
    seasonal_amplitude: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Amplitude of seasonal (sinusoidal) demand variation. "
                    "0.0 = no seasonality, 0.2 = ±20% swing over a year.",
    )
