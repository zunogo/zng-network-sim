"""Station & infrastructure CapEx — §5.4."""

from pydantic import BaseModel, Field


class StationConfig(BaseModel):
    """Station-level infrastructure inputs."""

    cabinet_cost: float = Field(default=50_000.0, ge=0, description="Physical housing, cooling, HMI (₹)")
    site_prep_cost: float = Field(default=30_000.0, ge=0, description="Civil works, earthing, pads (₹)")
    grid_connection_cost: float = Field(default=500_000.0, ge=0, le=2_000_000.0, description="Transformer, cabling (₹)")
    software_cost: float = Field(default=100_000.0, ge=0, description="One-time SMS + app cost (₹)")
    security_deposit: float = Field(default=20_000.0, ge=0, description="Real estate deposit (₹)")
    num_stations: int = Field(default=5, ge=1, description="Number of stations in the network")
    docks_per_station: int = Field(default=50, ge=1, le=100, description="Charger slots per station")
    operating_hours_per_day: float = Field(default=21.0, gt=0, le=24.0, description="Hours/day station operates")
    battery_float_pct: float = Field(
        default=0.10, ge=0, le=1.0,
        description="Float battery inventory as fraction of (packs_on_vehicles + packs_in_docks). "
                    "e.g. 0.10 = 10% extra packs for logistics buffer.",
    )