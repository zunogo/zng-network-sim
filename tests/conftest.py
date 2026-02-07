"""Shared test fixtures — sample configs matching base_case.yaml."""

from __future__ import annotations

import pytest

from zng_simulator.config import (
    ChaosConfig,
    ChargerVariant,
    OpExConfig,
    PackSpec,
    RevenueConfig,
    Scenario,
    SimulationConfig,
    StationConfig,
    VehicleConfig,
)


@pytest.fixture
def vehicle() -> VehicleConfig:
    return VehicleConfig(
        name="Heavy 2W",
        packs_per_vehicle=2,
        pack_capacity_kwh=1.28,
        avg_daily_km=100,
        energy_consumption_wh_per_km=30,
        swap_time_minutes=2.0,
        range_anxiety_buffer_pct=0.20,
    )


@pytest.fixture
def pack() -> PackSpec:
    return PackSpec(
        name="1.28 kWh NMC",
        nominal_capacity_kwh=1.28,
        chemistry="NMC",
        unit_cost=15_000,
        cycle_life_to_retirement=1_200,
        cycle_degradation_rate_pct=0.05,
        calendar_aging_rate_pct_per_month=0.15,
        depth_of_discharge_pct=0.80,
        retirement_soh_pct=0.70,
        second_life_salvage_value=3_000,
        weight_kg=6.5,
        aggressiveness_multiplier=1.0,
        mtbf_hours=50_000,
        mttr_hours=4.0,
        repair_cost_per_event=2_000,
        replacement_threshold=3,
        full_replacement_cost=15_000,
        spare_packs_cost_per_station=30_000,
    )


@pytest.fixture
def budget_charger() -> ChargerVariant:
    return ChargerVariant(
        name="Budget-1kW",
        purchase_cost_per_slot=8_000,
        rated_power_w=1_000,
        charging_efficiency_pct=0.90,
        efficiency_decay_pct_per_year=0.005,
        mtbf_hours=8_000,
        mttr_hours=24,
        repair_cost_per_event=1_500,
        replacement_threshold=3,
        full_replacement_cost=7_500,
        spare_inventory_cost=8_000,
        expected_useful_life_years=7,
    )


@pytest.fixture
def premium_charger() -> ChargerVariant:
    return ChargerVariant(
        name="Premium-1kW",
        purchase_cost_per_slot=25_000,
        rated_power_w=1_000,
        charging_efficiency_pct=0.92,
        efficiency_decay_pct_per_year=0.003,
        mtbf_hours=40_000,
        mttr_hours=12,
        repair_cost_per_event=2_000,
        replacement_threshold=4,
        full_replacement_cost=20_000,
        spare_inventory_cost=25_000,
        expected_useful_life_years=10,
    )


@pytest.fixture
def station() -> StationConfig:
    return StationConfig(
        cabinet_cost=50_000,
        site_prep_cost=30_000,
        grid_connection_cost=25_000,
        software_cost=100_000,
        security_deposit=20_000,
        num_stations=5,
        docks_per_station=8,
        operating_hours_per_day=18,
    )


@pytest.fixture
def opex() -> OpExConfig:
    return OpExConfig(
        electricity_tariff_per_kwh=8.0,
        auxiliary_power_per_month=2_000,
        rent_per_month_per_station=15_000,
        preventive_maintenance_per_month_per_station=3_000,
        corrective_maintenance_per_month_per_station=1_000,
        insurance_per_month_per_station=2_000,
        logistics_per_month_per_station=5_000,
        pack_handling_labor_per_swap=2.0,
        overhead_per_month=50_000,
    )


@pytest.fixture
def revenue() -> RevenueConfig:
    return RevenueConfig(
        price_per_swap=40.0,
        initial_fleet_size=200,
        monthly_fleet_additions=50,
    )


@pytest.fixture
def chaos() -> ChaosConfig:
    return ChaosConfig(
        sabotage_pct_per_month=0.005,
        aggressiveness_index=1.0,
        thermal_throttling_factor=1.0,
    )


@pytest.fixture
def sim_config() -> SimulationConfig:
    return SimulationConfig(horizon_months=60)


@pytest.fixture
def scenario(
    vehicle: VehicleConfig,
    pack: PackSpec,
    budget_charger: ChargerVariant,
    premium_charger: ChargerVariant,
    station: StationConfig,
    opex: OpExConfig,
    revenue: RevenueConfig,
    chaos: ChaosConfig,
    sim_config: SimulationConfig,
) -> Scenario:
    return Scenario(
        vehicle=vehicle,
        pack=pack,
        charger_variants=[budget_charger, premium_charger],
        station=station,
        opex=opex,
        revenue=revenue,
        chaos=chaos,
        simulation=sim_config,
    )
