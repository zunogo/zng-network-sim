"""Tests for engine/cashflow.py — full simulation run."""

from __future__ import annotations

from zng_simulator.config import Scenario, ChargerVariant
from zng_simulator.engine.cashflow import run_simulation


def test_simulation_returns_correct_months(scenario: Scenario, budget_charger: ChargerVariant):
    result = run_simulation(scenario, budget_charger)
    assert len(result.months) == scenario.simulation.horizon_months


def test_fleet_ramps_correctly(scenario: Scenario, budget_charger: ChargerVariant):
    result = run_simulation(scenario, budget_charger)
    assert result.months[0].fleet_size == 200
    assert result.months[1].fleet_size == 250
    assert result.months[-1].fleet_size == 200 + 50 * 59


def test_revenue_positive(scenario: Scenario, budget_charger: ChargerVariant):
    result = run_simulation(scenario, budget_charger)
    for snap in result.months:
        assert snap.revenue > 0


def test_revenue_is_per_visit_not_per_pack(scenario: Scenario, budget_charger: ChargerVariant):
    """Revenue = swap_visits × price_per_swap.  NOT visits × packs × price."""
    result = run_simulation(scenario, budget_charger)
    s = result.months[0]
    expected_revenue = s.swap_visits * scenario.revenue.price_per_swap
    assert abs(s.revenue - expected_revenue) < 1.0


def test_cycles_equals_visits_times_packs(scenario: Scenario, budget_charger: ChargerVariant):
    """total_cycles = swap_visits × packs_per_vehicle."""
    result = run_simulation(scenario, budget_charger)
    for snap in result.months:
        assert snap.total_cycles == snap.swap_visits * scenario.vehicle.packs_per_vehicle


def test_cumulative_cf_starts_negative(scenario: Scenario, budget_charger: ChargerVariant):
    """Big CapEx in month 1 should make cumulative CF very negative."""
    result = run_simulation(scenario, budget_charger)
    assert result.months[0].cumulative_cash_flow < 0


def test_summary_totals_match(scenario: Scenario, budget_charger: ChargerVariant):
    result = run_simulation(scenario, budget_charger)
    total_rev = sum(s.revenue for s in result.months)
    total_opex = sum(s.opex_total for s in result.months)
    assert abs(result.summary.total_revenue - total_rev) < 1.0
    assert abs(result.summary.total_opex - total_opex) < 1.0


def test_cpc_waterfall_populated(scenario: Scenario, budget_charger: ChargerVariant):
    result = run_simulation(scenario, budget_charger)
    assert result.cpc_waterfall.total > 0
    assert result.cpc_waterfall.battery > 0
    assert result.cpc_waterfall.electricity > 0


def test_charger_tco_populated(scenario: Scenario, budget_charger: ChargerVariant):
    result = run_simulation(scenario, budget_charger)
    assert result.charger_tco.total_tco > 0
    assert result.charger_tco.expected_failures_over_horizon > 0


def test_premium_vs_budget(scenario: Scenario, budget_charger: ChargerVariant, premium_charger: ChargerVariant):
    """Both produce valid results; premium has fewer failures."""
    res_b = run_simulation(scenario, budget_charger)
    res_p = run_simulation(scenario, premium_charger)
    assert res_b.cpc_waterfall.total > 0
    assert res_p.cpc_waterfall.total > 0
    assert res_p.charger_tco.expected_failures_over_horizon < res_b.charger_tco.expected_failures_over_horizon
    ratio = res_p.cpc_waterfall.total / res_b.cpc_waterfall.total
    assert 0.5 < ratio < 2.0


def test_yaml_scenario_loads():
    """Test that base_case.yaml can be loaded into a Scenario."""
    import yaml
    from pathlib import Path

    yaml_path = Path(__file__).parent.parent / "scenarios" / "base_case.yaml"
    with open(yaml_path) as f:
        data = yaml.safe_load(f)
    scenario = Scenario(**data)
    assert len(scenario.charger_variants) == 3
    assert scenario.vehicle.name == "Heavy 2W"
