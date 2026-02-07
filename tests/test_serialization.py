"""Serialization round-trip tests — result models survive JSON encode/decode.

PRD §12.5: "Contracts first, extend never rewrite" — the result model
shapes must be stable and serializable for downstream consumers.
"""

from __future__ import annotations

import json

from zng_simulator.config import Scenario, ChargerVariant
from zng_simulator.engine.cashflow import run_simulation
from zng_simulator.models.results import (
    ChargerTCOBreakdown,
    CostPerCycleWaterfall,
    DerivedParams,
    MonthlySnapshot,
    PackTCOBreakdown,
    RunSummary,
    SimulationResult,
)


# ═══════════════════════════════════════════════════════════════════════════
# Individual model round-trips
# ═══════════════════════════════════════════════════════════════════════════

def test_derived_params_round_trip():
    """DerivedParams → JSON → DerivedParams preserves all fields."""
    original = DerivedParams(
        energy_per_swap_cycle_per_pack_kwh=1.024,
        energy_per_swap_cycle_per_vehicle_kwh=2.048,
        total_energy_per_vehicle_kwh=2.56,
        daily_energy_need_wh=3000.0,
        swap_visits_per_vehicle_per_day=1.4648,
        charge_time_minutes=85.33,
        effective_c_rate=0.7813,
        cycles_per_day_per_dock=12.66,
        pack_lifetime_cycles=600,
        total_docks=40,
        cycles_per_month_per_station=3038.4,
        total_network_cycles_per_month=15192.0,
        initial_fleet_size=200,
        packs_on_vehicles=400,
        packs_in_docks=40,
        total_packs=440,
    )
    json_str = original.model_dump_json()
    restored = DerivedParams.model_validate_json(json_str)
    assert restored == original


def test_cpc_waterfall_round_trip():
    """CostPerCycleWaterfall → JSON → CostPerCycleWaterfall."""
    original = CostPerCycleWaterfall(
        battery=20.0, charger=4.2, electricity=11.38,
        real_estate=4.92, maintenance=1.31, insurance=0.66,
        sabotage=0.74, logistics=1.64, overhead=3.28, total=48.13,
    )
    json_str = original.model_dump_json()
    restored = CostPerCycleWaterfall.model_validate_json(json_str)
    assert restored == original


def test_charger_tco_round_trip():
    """ChargerTCOBreakdown → JSON → ChargerTCOBreakdown."""
    original = ChargerTCOBreakdown(
        total_docks=40,
        purchase_cost=320000.0,
        scheduled_hours_per_year_per_dock=6570.0,
        fleet_operating_hours=1314000.0,
        availability=0.997,
        expected_failures_over_horizon=164.25,
        total_repair_cost=246375.0,
        num_replacements=54,
        total_replacement_cost=405000.0,
        total_downtime_hours=3942.0,
        lost_revenue_from_downtime=50000.0,
        spare_inventory_cost=40000.0,
        total_tco=1061375.0,
        cycles_served_over_horizon=920000.0,
        cost_per_cycle=1.1536,
    )
    json_str = original.model_dump_json()
    restored = ChargerTCOBreakdown.model_validate_json(json_str)
    assert restored == original


def test_pack_tco_round_trip():
    """PackTCOBreakdown → JSON → PackTCOBreakdown."""
    original = PackTCOBreakdown(
        total_packs=440,
        fleet_operating_hours=14454000.0,
        availability=0.99992,
        expected_failures=289.08,
        total_repair_cost=578160.0,
        num_replacements=96,
        total_replacement_cost=1440000.0,
        total_downtime_hours=1156.32,
        lost_revenue_from_downtime=15000.0,
        spare_inventory_cost=150000.0,
        total_failure_tco=2183160.0,
        failure_cost_per_cycle=2.37,
    )
    json_str = original.model_dump_json()
    restored = PackTCOBreakdown.model_validate_json(json_str)
    assert restored == original


def test_monthly_snapshot_round_trip():
    """MonthlySnapshot → JSON → MonthlySnapshot."""
    cpc = CostPerCycleWaterfall(
        battery=20.0, charger=4.2, electricity=11.38,
        real_estate=4.92, maintenance=1.31, insurance=0.66,
        sabotage=0.74, logistics=1.64, overhead=3.28, total=48.13,
    )
    original = MonthlySnapshot(
        month=1, fleet_size=200, swap_visits=8789, total_cycles=17578,
        revenue=351560.0, opex_total=250000.0, capex_this_month=5000000.0,
        net_cash_flow=-4898440.0, cumulative_cash_flow=-4898440.0,
        cost_per_cycle=cpc,
    )
    json_str = original.model_dump_json()
    restored = MonthlySnapshot.model_validate_json(json_str)
    assert restored == original


def test_run_summary_round_trip():
    """RunSummary → JSON → RunSummary."""
    original = RunSummary(
        charger_variant_name="Budget-1kW",
        total_revenue=50000000.0,
        total_opex=30000000.0,
        total_capex=10000000.0,
        total_net_cash_flow=10000000.0,
        avg_cost_per_cycle=48.13,
        break_even_month=18,
    )
    json_str = original.model_dump_json()
    restored = RunSummary.model_validate_json(json_str)
    assert restored == original

    # Also test with break_even_month = None
    original_no_be = RunSummary(
        charger_variant_name="Expensive",
        total_revenue=1000.0, total_opex=5000.0,
        total_capex=100000.0, total_net_cash_flow=-104000.0,
        avg_cost_per_cycle=200.0, break_even_month=None,
    )
    json_str2 = original_no_be.model_dump_json()
    restored2 = RunSummary.model_validate_json(json_str2)
    assert restored2.break_even_month is None


# ═══════════════════════════════════════════════════════════════════════════
# Full SimulationResult round-trip (from actual engine run)
# ═══════════════════════════════════════════════════════════════════════════

def test_full_simulation_result_round_trip(
    scenario: Scenario, budget_charger: ChargerVariant,
):
    """Run the engine, serialize result to JSON, deserialize, compare.
    This tests the ENTIRE result model tree in one shot.
    """
    result = run_simulation(scenario, budget_charger)

    # Serialize
    json_str = result.model_dump_json()

    # Verify it's valid JSON
    parsed = json.loads(json_str)
    assert isinstance(parsed, dict)
    assert "months" in parsed
    assert "summary" in parsed
    assert "derived" in parsed
    assert "cpc_waterfall" in parsed
    assert "charger_tco" in parsed
    assert "pack_tco" in parsed

    # Deserialize
    restored = SimulationResult.model_validate_json(json_str)

    # Compare key fields
    assert restored.scenario_id == result.scenario_id
    assert restored.charger_variant_id == result.charger_variant_id
    assert len(restored.months) == len(result.months)
    assert restored.summary.total_revenue == result.summary.total_revenue
    assert restored.summary.break_even_month == result.summary.break_even_month
    assert restored.derived.total_docks == result.derived.total_docks
    assert restored.derived.total_packs == result.derived.total_packs
    assert restored.cpc_waterfall.total == result.cpc_waterfall.total
    assert restored.charger_tco.total_tco == result.charger_tco.total_tco
    assert restored.pack_tco.total_failure_tco == result.pack_tco.total_failure_tco

    # Compare month-by-month
    for orig_m, rest_m in zip(result.months, restored.months):
        assert rest_m.month == orig_m.month
        assert rest_m.fleet_size == orig_m.fleet_size
        assert rest_m.revenue == orig_m.revenue
        assert rest_m.cumulative_cash_flow == orig_m.cumulative_cash_flow


def test_simulation_result_dict_round_trip(
    scenario: Scenario, budget_charger: ChargerVariant,
):
    """SimulationResult → dict → SimulationResult (for YAML/config use)."""
    result = run_simulation(scenario, budget_charger)

    as_dict = result.model_dump()
    assert isinstance(as_dict, dict)

    restored = SimulationResult.model_validate(as_dict)
    assert restored.summary.total_revenue == result.summary.total_revenue
    assert restored.cpc_waterfall.total == result.cpc_waterfall.total
