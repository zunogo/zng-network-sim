"""Top-level scenario — bundles all §5 inputs."""

from pydantic import BaseModel, Field

from zng_simulator.config.vehicle import VehicleConfig
from zng_simulator.config.battery import PackSpec
from zng_simulator.config.charger import ChargerVariant
from zng_simulator.config.station import StationConfig
from zng_simulator.config.opex import OpExConfig
from zng_simulator.config.revenue import RevenueConfig
from zng_simulator.config.chaos import ChaosConfig


class SimulationConfig(BaseModel):
    """Simulation-level settings."""

    horizon_months: int = Field(default=60, ge=1, description="Simulation horizon (months)")
    discount_rate_annual: float = Field(default=0.12, ge=0, description="Annual discount rate (for future phases)")


class Scenario(BaseModel):
    """Complete input bundle for one simulation run."""

    vehicle: VehicleConfig = Field(default_factory=VehicleConfig)
    pack: PackSpec = Field(default_factory=PackSpec)
    charger_variants: list[ChargerVariant] = Field(default_factory=lambda: [ChargerVariant()])
    station: StationConfig = Field(default_factory=StationConfig)
    opex: OpExConfig = Field(default_factory=OpExConfig)
    revenue: RevenueConfig = Field(default_factory=RevenueConfig)
    chaos: ChaosConfig = Field(default_factory=ChaosConfig)
    simulation: SimulationConfig = Field(default_factory=SimulationConfig)
