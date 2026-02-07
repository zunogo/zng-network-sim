"""Fully-loaded cost per cycle — the 9-component waterfall (§6.4).

Each component = some monthly cost ÷ monthly cycles, or
asset cost ÷ lifetime cycles.
"""

from __future__ import annotations

from zng_simulator.config.battery import PackSpec
from zng_simulator.config.charger import ChargerVariant
from zng_simulator.config.opex import OpExConfig
from zng_simulator.config.chaos import ChaosConfig
from zng_simulator.config.station import StationConfig
from zng_simulator.config.vehicle import VehicleConfig
from zng_simulator.models.results import (
    ChargerTCOBreakdown,
    CostPerCycleWaterfall,
    DerivedParams,
    PackTCOBreakdown,
)


def compute_cpc_waterfall(
    derived: DerivedParams,
    pack: PackSpec,
    charger: ChargerVariant,
    opex: OpExConfig,
    chaos: ChaosConfig,
    station: StationConfig,
    vehicle: VehicleConfig,
    charger_tco: ChargerTCOBreakdown,
    pack_tco: PackTCOBreakdown,
) -> CostPerCycleWaterfall:
    """Compute the 9-component cost-per-cycle waterfall.

    Battery component = degradation cost + pack failure cost.
    Every formula matches §6.4 and §12.6.4 of the PRD.
    """
    cycles_per_month = derived.cycles_per_month_per_station
    num_stations = station.num_stations
    total_cycles_per_month = derived.total_network_cycles_per_month

    # Guard against division by zero
    if total_cycles_per_month <= 0:
        return CostPerCycleWaterfall(
            battery=0, charger=0, electricity=0, real_estate=0,
            maintenance=0, insurance=0, sabotage=0, logistics=0,
            overhead=0, total=0,
        )

    # 1. Battery: degradation + random failure costs
    #    Degradation: (pack_cost − salvage) / lifetime_cycles
    #    Failures:    pack_tco.failure_cost_per_cycle (fleet-level MTBF)
    cpc_battery_degradation = (
        (pack.unit_cost - pack.second_life_salvage_value) / derived.pack_lifetime_cycles
        if derived.pack_lifetime_cycles > 0
        else 0.0
    )
    cpc_battery = cpc_battery_degradation + pack_tco.failure_cost_per_cycle

    # 2. Charger: from TCO model
    cpc_charger = charger_tco.cost_per_cycle

    # 3. Electricity: (pack_capacity / efficiency) × tariff
    energy_drawn_kwh = pack.nominal_capacity_kwh / charger.charging_efficiency_pct if charger.charging_efficiency_pct > 0 else 0.0
    cpc_electricity = energy_drawn_kwh * opex.electricity_tariff_per_kwh

    # 4. Real estate: rent per station / cycles per month per station
    cpc_real_estate = (
        opex.rent_per_month_per_station / cycles_per_month
        if cycles_per_month > 0
        else 0.0
    )

    # 5. Maintenance: (preventive + corrective) per station / cycles per month per station
    monthly_maintenance = (
        opex.preventive_maintenance_per_month_per_station
        + opex.corrective_maintenance_per_month_per_station
    )
    cpc_maintenance = monthly_maintenance / cycles_per_month if cycles_per_month > 0 else 0.0

    # 6. Insurance: premium per station / cycles per month per station
    cpc_insurance = (
        opex.insurance_per_month_per_station / cycles_per_month
        if cycles_per_month > 0
        else 0.0
    )

    # 7. Sabotage: expected monthly pack loss value / total network cycles per month
    #    total_packs ≈ packs_per_vehicle × fleet (we use a reference fleet for steady-state)
    #    We allocate sabotage per-cycle at the network level.
    #    Monthly loss = sabotage% × total_packs × pack_cost
    #    For CPC waterfall we use: sabotage% × pack_cost (per-pack basis, amortised to cycle)
    #    = (sabotage_pct × pack_cost × packs_across_network) / total_network_cycles_per_month
    #    Simplification: sabotage_pct × pack_cost / (cycles_per_pack_per_month)
    #    cycles_per_pack_per_month ≈ pack sees some fraction of total cycles
    #    Simpler: sabotage_pct × pack_cost (monthly loss per pack) spread over cycles that pack does
    #    A pack does ~cycles_per_day × 30 / (total_packs / total_docks) cycles per month — complex.
    #    Phase 1 simple formula: sabotage_pct × pack_cost per month, divided by cycles per dock per month.
    sabotage_monthly_loss_per_station = (
        chaos.sabotage_pct_per_month
        * station.docks_per_station  # proxy for packs at station
        * pack.unit_cost
    )
    cpc_sabotage = sabotage_monthly_loss_per_station / cycles_per_month if cycles_per_month > 0 else 0.0

    # 8. Logistics: rebalancing cost per station / cycles per month per station
    cpc_logistics = (
        opex.logistics_per_month_per_station / cycles_per_month
        if cycles_per_month > 0
        else 0.0
    )

    # 9. Overhead: network-wide overhead / total network cycles per month
    cpc_overhead = opex.overhead_per_month / total_cycles_per_month if total_cycles_per_month > 0 else 0.0

    total = (
        cpc_battery + cpc_charger + cpc_electricity + cpc_real_estate
        + cpc_maintenance + cpc_insurance + cpc_sabotage + cpc_logistics + cpc_overhead
    )

    return CostPerCycleWaterfall(
        battery=round(cpc_battery, 4),
        charger=round(cpc_charger, 4),
        electricity=round(cpc_electricity, 4),
        real_estate=round(cpc_real_estate, 4),
        maintenance=round(cpc_maintenance, 4),
        insurance=round(cpc_insurance, 4),
        sabotage=round(cpc_sabotage, 4),
        logistics=round(cpc_logistics, 4),
        overhead=round(cpc_overhead, 4),
        total=round(total, 4),
    )
