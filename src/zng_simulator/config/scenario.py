"""Top-level scenario — bundles all §5 inputs."""

from typing import Literal

from pydantic import BaseModel, Field

from zng_simulator.config.vehicle import VehicleConfig
from zng_simulator.config.battery import PackSpec
from zng_simulator.config.charger import ChargerVariant
from zng_simulator.config.station import StationConfig
from zng_simulator.config.opex import OpExConfig
from zng_simulator.config.revenue import RevenueConfig
from zng_simulator.config.chaos import ChaosConfig
from zng_simulator.config.demand import DemandConfig
from zng_simulator.config.finance import FinanceConfig


class SimulationConfig(BaseModel):
    """Simulation-level settings.

    Phase 1 uses only ``horizon_months`` and ``discount_rate_annual``.
    Phase 2 adds engine selection, random seed, and Monte-Carlo run count.
    """

    horizon_months: int = Field(default=60, ge=1, description="Simulation horizon (months)")
    discount_rate_annual: float = Field(default=0.12, ge=0, description="Annual discount rate")

    # --- Phase 2: engine selection -----------------------------------------------
    engine: Literal["static", "stochastic"] = Field(
        default="static",
        description="Engine type: 'static' (Phase 1 deterministic) or "
                    "'stochastic' (Phase 2 Monte-Carlo with demand noise, "
                    "degradation cohorts, and charger failure draws).",
    )
    random_seed: int | None = Field(
        default=None,
        description="Optional RNG seed for reproducible stochastic runs. "
                    "None = non-deterministic.",
    )
    monte_carlo_runs: int = Field(
        default=100,
        ge=1,
        le=10_000,
        description="Number of Monte-Carlo iterations when engine='stochastic'. "
                    "Ignored in static mode. 100 is a good starting point; "
                    "1,000+ for bankability reports.",
    )


class Scenario(BaseModel):
    """Complete input bundle for one simulation run."""

    vehicle: VehicleConfig = Field(default_factory=VehicleConfig)
    pack: PackSpec = Field(default_factory=PackSpec)
    charger_variants: list[ChargerVariant] = Field(default_factory=lambda: [ChargerVariant()])
    station: StationConfig = Field(default_factory=StationConfig)
    opex: OpExConfig = Field(default_factory=OpExConfig)
    revenue: RevenueConfig = Field(default_factory=RevenueConfig)
    chaos: ChaosConfig = Field(default_factory=ChaosConfig)
    demand: DemandConfig = Field(default_factory=DemandConfig)
    finance: FinanceConfig = Field(default_factory=FinanceConfig)
    simulation: SimulationConfig = Field(default_factory=SimulationConfig)
