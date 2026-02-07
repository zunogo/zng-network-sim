"""Operating expenditure — §5.5."""

from pydantic import BaseModel, Field


class OpExConfig(BaseModel):
    """Monthly operating cost inputs."""

    electricity_tariff_per_kwh: float = Field(default=6.50, ge=0, description="Blended tariff (₹/kWh)")
    auxiliary_power_per_month: float = Field(default=2_000.0, ge=0, description="Cooling + standby per station (₹)")
    rent_per_month_per_station: float = Field(default=15_000.0, ge=0, description="Monthly rent per station (₹)")
    preventive_maintenance_per_month_per_station: float = Field(
        default=3_000.0, ge=0, description="Scheduled maintenance per station (₹)",
    )
    corrective_maintenance_per_month_per_station: float = Field(
        default=1_000.0, ge=0, description="Wear-item replacements per station (₹)",
    )
    insurance_per_month_per_station: float = Field(default=2_000.0, ge=0, description="Insurance premium per station (₹)")
    logistics_per_month_per_station: float = Field(
        default=5_000.0, ge=0, description="Battery rebalancing cost per station (₹)",
    )
    pack_handling_labor_per_swap: float = Field(default=2.0, ge=0, description="Labor cost per swap event (₹)")
    overhead_per_month: float = Field(default=20_000.0, ge=0, description="Network-wide admin + software (₹)")
