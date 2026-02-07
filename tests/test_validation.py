"""Pydantic validation tests — ensure invalid inputs are rejected.

Tests every config model for boundary violations: negative values,
out-of-range percentages, zero where positive is required, etc.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from zng_simulator.config import (
    VehicleConfig,
    PackSpec,
    ChargerVariant,
    StationConfig,
    OpExConfig,
    RevenueConfig,
    ChaosConfig,
    DemandConfig,
    SimulationConfig,
    Scenario,
)


# ═══════════════════════════════════════════════════════════════════════════
# VehicleConfig
# ═══════════════════════════════════════════════════════════════════════════

class TestVehicleValidation:
    """VehicleConfig field constraints."""

    def test_defaults_are_valid(self):
        v = VehicleConfig()
        assert v.packs_per_vehicle >= 1

    def test_zero_packs_rejected(self):
        with pytest.raises(ValidationError):
            VehicleConfig(packs_per_vehicle=0)

    def test_negative_packs_rejected(self):
        with pytest.raises(ValidationError):
            VehicleConfig(packs_per_vehicle=-1)

    def test_packs_above_max_rejected(self):
        with pytest.raises(ValidationError):
            VehicleConfig(packs_per_vehicle=5)  # le=4

    def test_zero_capacity_rejected(self):
        with pytest.raises(ValidationError):
            VehicleConfig(pack_capacity_kwh=0)  # gt=0

    def test_negative_capacity_rejected(self):
        with pytest.raises(ValidationError):
            VehicleConfig(pack_capacity_kwh=-1.0)

    def test_zero_daily_km_rejected(self):
        with pytest.raises(ValidationError):
            VehicleConfig(avg_daily_km=0)

    def test_zero_wh_per_km_rejected(self):
        with pytest.raises(ValidationError):
            VehicleConfig(energy_consumption_wh_per_km=0)

    def test_zero_swap_time_rejected(self):
        with pytest.raises(ValidationError):
            VehicleConfig(swap_time_minutes=0)

    def test_buffer_above_one_rejected(self):
        with pytest.raises(ValidationError):
            VehicleConfig(range_anxiety_buffer_pct=1.5)

    def test_negative_buffer_rejected(self):
        with pytest.raises(ValidationError):
            VehicleConfig(range_anxiety_buffer_pct=-0.1)

    def test_edge_valid_values(self):
        """Boundary values that should be accepted."""
        v = VehicleConfig(
            packs_per_vehicle=1,     # ge=1
            pack_capacity_kwh=0.01,  # gt=0
            range_anxiety_buffer_pct=0.0,  # ge=0
        )
        assert v.packs_per_vehicle == 1
        v2 = VehicleConfig(
            packs_per_vehicle=4,     # le=4
            range_anxiety_buffer_pct=1.0,  # le=1.0
        )
        assert v2.packs_per_vehicle == 4


# ═══════════════════════════════════════════════════════════════════════════
# PackSpec
# ═══════════════════════════════════════════════════════════════════════════

class TestPackValidation:
    """PackSpec field constraints."""

    def test_defaults_are_valid(self):
        p = PackSpec()
        assert p.nominal_capacity_kwh > 0

    def test_zero_capacity_rejected(self):
        with pytest.raises(ValidationError):
            PackSpec(nominal_capacity_kwh=0)

    def test_negative_unit_cost_rejected(self):
        with pytest.raises(ValidationError):
            PackSpec(unit_cost=-1)

    def test_zero_cycle_life_rejected(self):
        with pytest.raises(ValidationError):
            PackSpec(cycle_life_to_retirement=0)

    def test_zero_degradation_rate_rejected(self):
        with pytest.raises(ValidationError):
            PackSpec(cycle_degradation_rate_pct=0)  # gt=0

    def test_dod_above_one_rejected(self):
        with pytest.raises(ValidationError):
            PackSpec(depth_of_discharge_pct=1.1)

    def test_retirement_soh_above_one_rejected(self):
        with pytest.raises(ValidationError):
            PackSpec(retirement_soh_pct=1.1)

    def test_zero_weight_rejected(self):
        with pytest.raises(ValidationError):
            PackSpec(weight_kg=0)

    def test_zero_mtbf_rejected(self):
        with pytest.raises(ValidationError):
            PackSpec(mtbf_hours=0)

    def test_zero_mttr_rejected(self):
        with pytest.raises(ValidationError):
            PackSpec(mttr_hours=0)

    def test_zero_replacement_threshold_rejected(self):
        with pytest.raises(ValidationError):
            PackSpec(replacement_threshold=0)

    def test_zero_cost_allowed(self):
        """unit_cost=0 is valid (ge=0) — free battery hypothetical."""
        p = PackSpec(unit_cost=0)
        assert p.unit_cost == 0


# ═══════════════════════════════════════════════════════════════════════════
# ChargerVariant
# ═══════════════════════════════════════════════════════════════════════════

class TestChargerValidation:
    """ChargerVariant field constraints."""

    def test_defaults_are_valid(self):
        c = ChargerVariant()
        assert c.rated_power_w > 0

    def test_zero_power_rejected(self):
        with pytest.raises(ValidationError):
            ChargerVariant(rated_power_w=0)

    def test_efficiency_above_one_rejected(self):
        with pytest.raises(ValidationError):
            ChargerVariant(charging_efficiency_pct=1.1)

    def test_zero_efficiency_rejected(self):
        with pytest.raises(ValidationError):
            ChargerVariant(charging_efficiency_pct=0)  # gt=0

    def test_zero_mtbf_rejected(self):
        with pytest.raises(ValidationError):
            ChargerVariant(mtbf_hours=0)

    def test_zero_mttr_rejected(self):
        with pytest.raises(ValidationError):
            ChargerVariant(mttr_hours=0)

    def test_zero_useful_life_rejected(self):
        with pytest.raises(ValidationError):
            ChargerVariant(expected_useful_life_years=0)

    def test_negative_cost_rejected(self):
        with pytest.raises(ValidationError):
            ChargerVariant(purchase_cost_per_slot=-100)

    def test_zero_replacement_threshold_rejected(self):
        with pytest.raises(ValidationError):
            ChargerVariant(replacement_threshold=0)


# ═══════════════════════════════════════════════════════════════════════════
# StationConfig
# ═══════════════════════════════════════════════════════════════════════════

class TestStationValidation:
    """StationConfig field constraints."""

    def test_defaults_are_valid(self):
        s = StationConfig()
        assert s.num_stations >= 1

    def test_zero_stations_rejected(self):
        with pytest.raises(ValidationError):
            StationConfig(num_stations=0)

    def test_zero_docks_rejected(self):
        with pytest.raises(ValidationError):
            StationConfig(docks_per_station=0)

    def test_zero_hours_rejected(self):
        with pytest.raises(ValidationError):
            StationConfig(operating_hours_per_day=0)  # gt=0

    def test_hours_above_24_rejected(self):
        with pytest.raises(ValidationError):
            StationConfig(operating_hours_per_day=25)

    def test_negative_cost_rejected(self):
        with pytest.raises(ValidationError):
            StationConfig(cabinet_cost=-1)


# ═══════════════════════════════════════════════════════════════════════════
# OpExConfig
# ═══════════════════════════════════════════════════════════════════════════

class TestOpExValidation:
    """OpExConfig field constraints."""

    def test_defaults_are_valid(self):
        o = OpExConfig()
        assert o.electricity_tariff_per_kwh >= 0

    def test_negative_tariff_rejected(self):
        with pytest.raises(ValidationError):
            OpExConfig(electricity_tariff_per_kwh=-1)

    def test_negative_rent_rejected(self):
        with pytest.raises(ValidationError):
            OpExConfig(rent_per_month_per_station=-1)

    def test_negative_labor_rejected(self):
        with pytest.raises(ValidationError):
            OpExConfig(pack_handling_labor_per_swap=-1)

    def test_zero_values_allowed(self):
        """All OpEx fields accept 0 (ge=0)."""
        o = OpExConfig(
            electricity_tariff_per_kwh=0,
            rent_per_month_per_station=0,
            overhead_per_month=0,
        )
        assert o.electricity_tariff_per_kwh == 0


# ═══════════════════════════════════════════════════════════════════════════
# RevenueConfig
# ═══════════════════════════════════════════════════════════════════════════

class TestRevenueValidation:
    """RevenueConfig field constraints."""

    def test_defaults_are_valid(self):
        r = RevenueConfig()
        assert r.initial_fleet_size >= 1

    def test_zero_fleet_rejected(self):
        with pytest.raises(ValidationError):
            RevenueConfig(initial_fleet_size=0)

    def test_negative_price_rejected(self):
        with pytest.raises(ValidationError):
            RevenueConfig(price_per_swap=-10)

    def test_negative_fleet_additions_rejected(self):
        with pytest.raises(ValidationError):
            RevenueConfig(monthly_fleet_additions=-1)

    def test_zero_price_allowed(self):
        """Free swaps hypothetical (ge=0)."""
        r = RevenueConfig(price_per_swap=0)
        assert r.price_per_swap == 0


# ═══════════════════════════════════════════════════════════════════════════
# ChaosConfig
# ═══════════════════════════════════════════════════════════════════════════

class TestChaosValidation:
    """ChaosConfig field constraints."""

    def test_defaults_are_valid(self):
        c = ChaosConfig()
        assert 0 <= c.sabotage_pct_per_month <= 1.0

    def test_sabotage_above_one_rejected(self):
        with pytest.raises(ValidationError):
            ChaosConfig(sabotage_pct_per_month=1.5)

    def test_negative_sabotage_rejected(self):
        with pytest.raises(ValidationError):
            ChaosConfig(sabotage_pct_per_month=-0.01)

    def test_aggressiveness_too_low_rejected(self):
        with pytest.raises(ValidationError):
            ChaosConfig(aggressiveness_index=0.05)  # ge=0.1

    def test_throttling_above_max_rejected(self):
        with pytest.raises(ValidationError):
            ChaosConfig(thermal_throttling_factor=2.5)  # le=2.0


# ═══════════════════════════════════════════════════════════════════════════
# DemandConfig (Phase 2)
# ═══════════════════════════════════════════════════════════════════════════

class TestDemandValidation:
    """DemandConfig field constraints."""

    def test_defaults_are_valid(self):
        d = DemandConfig()
        assert d.distribution in ("poisson", "gamma")
        assert d.volatility >= 0

    def test_invalid_distribution_rejected(self):
        with pytest.raises(ValidationError):
            DemandConfig(distribution="uniform")

    def test_negative_volatility_rejected(self):
        with pytest.raises(ValidationError):
            DemandConfig(volatility=-0.1)

    def test_volatility_above_max_rejected(self):
        with pytest.raises(ValidationError):
            DemandConfig(volatility=2.5)  # le=2.0

    def test_zero_volatility_allowed(self):
        """Zero volatility = deterministic demand (ge=0)."""
        d = DemandConfig(volatility=0.0)
        assert d.volatility == 0.0

    def test_negative_weekend_factor_rejected(self):
        with pytest.raises(ValidationError):
            DemandConfig(weekend_factor=-0.1)

    def test_weekend_factor_above_max_rejected(self):
        with pytest.raises(ValidationError):
            DemandConfig(weekend_factor=2.5)

    def test_negative_seasonal_amplitude_rejected(self):
        with pytest.raises(ValidationError):
            DemandConfig(seasonal_amplitude=-0.1)

    def test_seasonal_amplitude_above_max_rejected(self):
        with pytest.raises(ValidationError):
            DemandConfig(seasonal_amplitude=1.5)

    def test_gamma_with_high_volatility(self):
        """Gamma distribution with high CoV is valid."""
        d = DemandConfig(distribution="gamma", volatility=1.5)
        assert d.distribution == "gamma"
        assert d.volatility == 1.5


# ═══════════════════════════════════════════════════════════════════════════
# SimulationConfig (extended for Phase 2)
# ═══════════════════════════════════════════════════════════════════════════

class TestSimulationValidation:
    """SimulationConfig field constraints."""

    def test_defaults_are_valid(self):
        s = SimulationConfig()
        assert s.horizon_months >= 1
        assert s.engine == "static"
        assert s.monte_carlo_runs >= 1

    def test_zero_horizon_rejected(self):
        with pytest.raises(ValidationError):
            SimulationConfig(horizon_months=0)

    def test_negative_discount_rate_rejected(self):
        with pytest.raises(ValidationError):
            SimulationConfig(discount_rate_annual=-0.1)

    def test_invalid_engine_rejected(self):
        with pytest.raises(ValidationError):
            SimulationConfig(engine="montecarlo")

    def test_stochastic_engine_accepted(self):
        s = SimulationConfig(engine="stochastic")
        assert s.engine == "stochastic"

    def test_zero_mc_runs_rejected(self):
        with pytest.raises(ValidationError):
            SimulationConfig(monte_carlo_runs=0)

    def test_mc_runs_above_max_rejected(self):
        with pytest.raises(ValidationError):
            SimulationConfig(monte_carlo_runs=10_001)  # le=10_000

    def test_random_seed_none_allowed(self):
        s = SimulationConfig(random_seed=None)
        assert s.random_seed is None

    def test_random_seed_integer_allowed(self):
        s = SimulationConfig(random_seed=42)
        assert s.random_seed == 42


# ═══════════════════════════════════════════════════════════════════════════
# ChargerVariant (extended for Phase 2)
# ═══════════════════════════════════════════════════════════════════════════

class TestChargerPhase2Validation:
    """Phase 2 extensions on ChargerVariant."""

    def test_default_failure_distribution(self):
        c = ChargerVariant()
        assert c.failure_distribution == "exponential"
        assert c.weibull_shape == 1.0

    def test_invalid_distribution_rejected(self):
        with pytest.raises(ValidationError):
            ChargerVariant(failure_distribution="normal")

    def test_weibull_accepted(self):
        c = ChargerVariant(failure_distribution="weibull", weibull_shape=1.5)
        assert c.failure_distribution == "weibull"

    def test_zero_weibull_shape_rejected(self):
        with pytest.raises(ValidationError):
            ChargerVariant(weibull_shape=0)  # gt=0

    def test_negative_weibull_shape_rejected(self):
        with pytest.raises(ValidationError):
            ChargerVariant(weibull_shape=-1.0)

    def test_infant_mortality_shape(self):
        """β < 1 = infant mortality — valid."""
        c = ChargerVariant(failure_distribution="weibull", weibull_shape=0.5)
        assert c.weibull_shape == 0.5

    def test_strong_wearout_shape(self):
        """β > 1 = wear-out — valid."""
        c = ChargerVariant(failure_distribution="weibull", weibull_shape=3.0)
        assert c.weibull_shape == 3.0


# ═══════════════════════════════════════════════════════════════════════════
# Scenario (composite)
# ═══════════════════════════════════════════════════════════════════════════

class TestScenarioValidation:
    """Scenario-level validation."""

    def test_defaults_are_valid(self):
        s = Scenario()
        assert len(s.charger_variants) >= 1

    def test_nested_invalid_propagates(self):
        """Invalid nested config should fail Scenario creation."""
        with pytest.raises(ValidationError):
            Scenario(vehicle=VehicleConfig(packs_per_vehicle=0))

    def test_scenario_includes_demand(self):
        """Scenario now includes demand config."""
        s = Scenario()
        assert s.demand is not None
        assert s.demand.distribution in ("poisson", "gamma")

    def test_scenario_stochastic_engine(self):
        """Scenario can be configured for stochastic engine."""
        s = Scenario(simulation=SimulationConfig(engine="stochastic", monte_carlo_runs=500))
        assert s.simulation.engine == "stochastic"
        assert s.simulation.monte_carlo_runs == 500
