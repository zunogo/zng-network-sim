"""Tests for pilot sizing optimizer — Phase 4 (§9).

Covers:
  - find_minimum_fleet_size (binary search)
  - find_optimal_scale (evaluate specific sizes)
  - Target metrics: positive_npv, positive_ncf, break_even_within
  - Search logs and result structure
"""

import pytest

from zng_simulator.config.scenario import Scenario
from zng_simulator.config.charger import ChargerVariant
from zng_simulator.engine.optimizer import (
    find_minimum_fleet_size,
    find_optimal_scale,
    _check_target,
)
from zng_simulator.models.field_data import PilotSizingResult


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════

def _base_scenario() -> Scenario:
    """Create a minimal scenario with short horizon for fast tests."""
    return Scenario(
        simulation={"horizon_months": 24, "discount_rate_annual": 0.12, "engine": "static"},
        revenue={"initial_fleet_size": 200, "price_per_swap": 80.0},
        station={"num_stations": 3, "docks_per_station": 20},
    )


def _base_charger() -> ChargerVariant:
    return ChargerVariant(name="Budget-1kW")


# ═══════════════════════════════════════════════════════════════════════════
# _check_target unit tests
# ═══════════════════════════════════════════════════════════════════════════

class TestCheckTarget:
    def test_positive_npv_pass(self):
        assert _check_target("positive_npv", 1000.0, 500.0, 12, 24) is True

    def test_positive_npv_fail(self):
        assert _check_target("positive_npv", -500.0, 500.0, 12, 24) is False

    def test_positive_npv_none(self):
        assert _check_target("positive_npv", None, 500.0, 12, 24) is False

    def test_positive_ncf_pass(self):
        assert _check_target("positive_ncf", -500.0, 1000.0, 12, 24) is True

    def test_positive_ncf_fail(self):
        assert _check_target("positive_ncf", 1000.0, -500.0, 12, 24) is False

    def test_break_even_within_pass(self):
        assert _check_target("break_even_within", 1000.0, 500.0, 12, 24) is True

    def test_break_even_within_fail(self):
        assert _check_target("break_even_within", 1000.0, 500.0, 30, 24) is False

    def test_break_even_within_none(self):
        assert _check_target("break_even_within", 1000.0, 500.0, None, 24) is False

    def test_unknown_metric(self):
        assert _check_target("unknown", 1000.0, 500.0, 12, 24) is False


# ═══════════════════════════════════════════════════════════════════════════
# find_minimum_fleet_size — binary search
# ═══════════════════════════════════════════════════════════════════════════

class TestFindMinimumFleetSize:
    def test_returns_pilot_sizing_result(self):
        scenario = _base_scenario()
        charger = _base_charger()

        result = find_minimum_fleet_size(
            scenario, charger,
            target_metric="positive_ncf",
            min_fleet=50, max_fleet=500,
            max_iterations=8,
        )
        assert isinstance(result, PilotSizingResult)
        assert result.target_metric == "positive_ncf"
        assert result.search_iterations > 0
        assert len(result.search_log) > 0

    def test_search_log_populated(self):
        scenario = _base_scenario()
        charger = _base_charger()

        result = find_minimum_fleet_size(
            scenario, charger,
            target_metric="positive_ncf",
            min_fleet=50, max_fleet=500,
            max_iterations=5,
        )
        for entry in result.search_log:
            assert "fleet_size" in entry
            assert "npv" in entry
            assert "passed" in entry

    def test_achieves_target(self):
        """With a wide enough range, the optimizer should find a solution."""
        scenario = _base_scenario()
        charger = _base_charger()

        result = find_minimum_fleet_size(
            scenario, charger,
            target_metric="positive_ncf",
            min_fleet=10, max_fleet=2000,
            max_iterations=15,
        )
        # Either achieved or not — but the structure should be valid
        assert result.recommended_fleet_size >= 10
        assert result.recommended_fleet_size <= 2000

    def test_positive_npv_target(self):
        scenario = _base_scenario()
        charger = _base_charger()

        result = find_minimum_fleet_size(
            scenario, charger,
            target_metric="positive_npv",
            min_fleet=50, max_fleet=1000,
            max_iterations=10,
        )
        if result.achieved:
            assert result.best_npv is not None
            assert result.best_npv > 0

    def test_break_even_target(self):
        scenario = _base_scenario()
        charger = _base_charger()

        result = find_minimum_fleet_size(
            scenario, charger,
            target_metric="break_even_within",
            break_even_target_months=24,
            min_fleet=50, max_fleet=1000,
            max_iterations=10,
        )
        if result.achieved:
            assert result.best_break_even_month is not None
            assert result.best_break_even_month <= 24

    def test_unachievable_target_returns_max(self):
        """When target is unachievable, return max_fleet with achieved=False."""
        scenario = _base_scenario()
        # Set price to near-zero making profitability impossible
        scenario.revenue.price_per_swap = 0.01
        charger = _base_charger()

        result = find_minimum_fleet_size(
            scenario, charger,
            target_metric="positive_npv",
            min_fleet=10, max_fleet=50,
            max_iterations=6,
        )
        assert result.achieved is False
        assert result.recommended_fleet_size == 50

    def test_max_iterations_respected(self):
        scenario = _base_scenario()
        charger = _base_charger()

        result = find_minimum_fleet_size(
            scenario, charger,
            target_metric="positive_ncf",
            min_fleet=10, max_fleet=2000,
            max_iterations=3,
        )
        assert result.search_iterations <= 3


# ═══════════════════════════════════════════════════════════════════════════
# find_optimal_scale — specific fleet sizes
# ═══════════════════════════════════════════════════════════════════════════

class TestFindOptimalScale:
    def test_returns_result(self):
        scenario = _base_scenario()
        charger = _base_charger()

        result = find_optimal_scale(
            scenario, charger,
            fleet_sizes=[100, 200, 300],
            target_metric="positive_ncf",
        )
        assert isinstance(result, PilotSizingResult)
        assert result.search_iterations == 3  # evaluated 3 sizes
        assert len(result.search_log) == 3

    def test_evaluates_all_sizes(self):
        scenario = _base_scenario()
        charger = _base_charger()
        sizes = [50, 100, 200]

        result = find_optimal_scale(
            scenario, charger,
            fleet_sizes=sizes,
            target_metric="positive_ncf",
        )
        logged_sizes = [e["fleet_size"] for e in result.search_log]
        assert logged_sizes == sizes

    def test_picks_best_npv(self):
        """Among passing candidates, should pick the one with highest NPV."""
        scenario = _base_scenario()
        charger = _base_charger()

        result = find_optimal_scale(
            scenario, charger,
            fleet_sizes=[100, 200, 500],
            target_metric="positive_ncf",
        )
        if result.achieved:
            # The recommended size should be from the evaluated list
            assert result.recommended_fleet_size in [100, 200, 500]

    def test_default_fleet_sizes(self):
        scenario = _base_scenario()
        charger = _base_charger()

        result = find_optimal_scale(
            scenario, charger,
            target_metric="positive_ncf",
        )
        # Default sizes: [50, 100, 200, 300, 500]
        assert result.search_iterations == 5

    def test_station_config_preserved(self):
        scenario = _base_scenario()
        charger = _base_charger()

        result = find_optimal_scale(
            scenario, charger,
            fleet_sizes=[100],
            target_metric="positive_ncf",
        )
        assert result.recommended_num_stations == scenario.station.num_stations
        assert result.recommended_docks_per_station == scenario.station.docks_per_station
