"""Tests for the investor unit economics PDF report.

Asserts the grounding contract: every value the report renders must
trace back to a simulator output, scenario field, or finance bundle —
never a literal, never filler when data is absent.
"""

from __future__ import annotations

from datetime import date

import pytest

from zng_simulator.config.scenario import Scenario
from zng_simulator.dashboard.reports.unit_economics import (
    _collect_report_data,
    build_unit_economics_pdf,
)
from zng_simulator.engine.orchestrator import run_engine
from zng_simulator.finance.bundle import compute_finance_bundle


@pytest.fixture
def static_run(scenario: Scenario):
    cv = scenario.charger_variants[0]
    result = run_engine(scenario, cv)
    bundle = compute_finance_bundle(result, cv, scenario)
    return scenario, result, cv, bundle


def test_pdf_smoke(static_run):
    scenario, result, _cv, bundle = static_run
    pdf = build_unit_economics_pdf(scenario, result, bundle, scenario_name="test")
    assert pdf.startswith(b"%PDF-")
    assert len(pdf) > 1024


def test_collected_data_matches_simulator_outputs(static_run):
    """Every value the report renders must equal a real field on the source objects."""
    scenario, result, cv, bundle = static_run
    data = _collect_report_data(scenario, result, bundle, mc_summary=None,
                                scenario_name=None, today=date(2026, 5, 7))

    # Cover / executive
    assert data["scenario_name"] is None
    assert data["generated_on"] == "2026-05-07"
    assert data["horizon_months"] == scenario.simulation.horizon_months
    assert data["engine"] == scenario.simulation.engine
    assert data["num_stations"] == scenario.station.num_stations
    assert data["total_docks"] == result.derived.total_docks
    assert data["fleet_size"] == scenario.revenue.initial_fleet_size
    assert data["total_packs"] == result.derived.total_packs
    assert data["charger_variant_name"] == cv.name

    # Headline KPIs — must be the literal field values, not transformed
    assert data["avg_cost_per_cycle"] == result.summary.avg_cost_per_cycle
    assert data["price_per_swap"] == scenario.revenue.price_per_swap
    assert data["npv"] == bundle.dcf.npv
    assert data["irr"] == bundle.dcf.irr
    assert data["discounted_payback_month"] == bundle.dcf.discounted_payback_month
    assert data["terminal_value"] == bundle.dcf.terminal_value

    # Horizon totals
    assert data["total_revenue"] == result.summary.total_revenue
    assert data["total_opex"] == result.summary.total_opex
    assert data["total_capex"] == result.summary.total_capex
    assert data["total_net_cash_flow"] == result.summary.total_net_cash_flow
    assert data["break_even_month"] == result.summary.break_even_month

    # Cost-per-cycle waterfall — every component is the simulator's value
    cpc = data["cpc"]
    w = result.cpc_waterfall
    assert cpc["battery"] == w.battery
    assert cpc["charger"] == w.charger
    assert cpc["electricity"] == w.electricity
    assert cpc["real_estate"] == w.real_estate
    assert cpc["maintenance"] == w.maintenance
    assert cpc["insurance"] == w.insurance
    assert cpc["sabotage"] == w.sabotage
    assert cpc["logistics"] == w.logistics
    assert cpc["overhead"] == w.overhead
    assert cpc["total"] == w.total

    # Cumulative PV trajectory
    assert data["cumulative_pv"] == [r.cumulative_pv for r in bundle.dcf.monthly_dcf]

    # Reliability
    rel = data["reliability"]
    assert rel["charger_availability"] == result.charger_tco.availability
    assert rel["pack_availability"] == result.pack_tco.availability
    assert rel["expected_charger_failures"] == result.charger_tco.expected_failures_over_horizon
    assert rel["expected_pack_failures"] == result.pack_tco.expected_failures

    # Per-station economics
    ps = data["per_station"]
    assert ps["cycles_per_dock_per_day"] == result.derived.cycles_per_day_per_dock
    assert ps["swap_visits_per_vehicle_per_day"] == result.derived.swap_visits_per_vehicle_per_day
    assert ps["cycles_per_month_per_station"] == result.derived.cycles_per_month_per_station
    assert ps["revenue_per_cycle"] == scenario.revenue.price_per_swap
    assert ps["cost_per_cycle"] == result.summary.avg_cost_per_cycle

    # Scenario configuration — strings derived from real fields, no fabrication
    cfg = data["config"]
    assert str(scenario.station.num_stations) in cfg["network"]
    assert str(scenario.station.docks_per_station) in cfg["network"]
    assert scenario.vehicle.name in cfg["fleet"]
    assert str(scenario.vehicle.packs_per_vehicle) in cfg["fleet"]
    assert scenario.pack.chemistry in cfg["pack"]
    assert cv.name in cfg["charger"]
    assert f"{int(scenario.revenue.price_per_swap)}" in cfg["pricing"]
    assert scenario.demand.distribution in cfg["demand"]
    assert scenario.simulation.engine in cfg["engine_horizon"]
    assert str(scenario.simulation.horizon_months) in cfg["engine_horizon"]

    # Operating insights — derived numbers must match what the engine produced
    insights = data["operating_insights"]
    assert insights["swaps_per_vehicle_per_day"] == result.derived.swap_visits_per_vehicle_per_day
    assert insights["cycles_per_dock_per_day"] == result.derived.cycles_per_day_per_dock
    # pack_lifetime_years = cycle_life / (cycles_per_pack_per_month * 12)
    cycles_per_pack_per_month = result.derived.total_network_cycles_per_month / result.derived.total_packs
    expected_life = scenario.pack.cycle_life_to_retirement / (cycles_per_pack_per_month * 12)
    assert insights["pack_lifetime_years"] == pytest.approx(expected_life, rel=1e-9)

    # Risk knobs — values must match scenario inputs exactly
    risk = data["risk_knobs"]
    assert risk["range_anxiety_buffer_pct"] == scenario.vehicle.range_anxiety_buffer_pct
    assert risk["cycle_degradation_rate_pct"] == scenario.pack.cycle_degradation_rate_pct
    assert risk["calendar_aging_rate_pct_per_month"] == scenario.pack.calendar_aging_rate_pct_per_month
    assert risk["sabotage_pct_per_month"] == scenario.chaos.sabotage_pct_per_month
    assert risk["charger_failure_distribution"] == cv.failure_distribution
    assert risk["charger_weibull_shape"] == cv.weibull_shape

    # Costs — CapEx breakdown + lumped per-station setup
    capex = data["costs"]["capex"]
    expected_setup = (
        scenario.station.cabinet_cost + scenario.station.site_prep_cost
        + scenario.station.grid_connection_cost + scenario.station.security_deposit
    )
    assert capex["per_station_setup"] == pytest.approx(expected_setup)
    assert capex["software_one_time"] == scenario.station.software_cost
    assert capex["charger_per_slot"] == cv.purchase_cost_per_slot
    assert capex["pack_unit_cost"] == scenario.pack.unit_cost
    assert capex["total_initial_capex"] == bundle.total_initial_capex

    # Costs — OpEx breakdown including lumped "other station" costs and fixed monthly burn
    opex = data["costs"]["opex"]
    o = scenario.opex
    expected_other = (
        o.preventive_maintenance_per_month_per_station
        + o.corrective_maintenance_per_month_per_station
        + o.insurance_per_month_per_station
        + o.logistics_per_month_per_station
        + o.auxiliary_power_per_month
    )
    expected_burn = (
        (o.rent_per_month_per_station + expected_other) * scenario.station.num_stations
        + o.overhead_per_month
    )
    assert opex["rent_per_station_monthly"] == o.rent_per_month_per_station
    assert opex["other_station_per_month"] == pytest.approx(expected_other)
    assert opex["overhead_monthly"] == o.overhead_per_month
    assert opex["electricity_tariff_per_kwh"] == o.electricity_tariff_per_kwh
    assert opex["labor_per_swap"] == o.pack_handling_labor_per_swap
    assert opex["fixed_monthly_burn"] == pytest.approx(expected_burn)

    # Assumptions
    a = data["assumptions"]
    assert a["discount_rate_annual"] == scenario.simulation.discount_rate_annual
    assert a["debt_pct_of_capex"] == scenario.finance.debt_pct_of_capex
    assert a["interest_rate_annual"] == scenario.finance.interest_rate_annual
    assert a["tax_rate"] == scenario.finance.tax_rate
    assert a["electricity_tariff_per_kwh"] == scenario.opex.electricity_tariff_per_kwh
    assert a["pack_unit_cost"] == scenario.pack.unit_cost
    assert a["charger_purchase_cost_per_slot"] == cv.purchase_cost_per_slot
    assert a["pack_mtbf_hours"] == scenario.pack.mtbf_hours
    assert a["pack_mttr_hours"] == scenario.pack.mttr_hours
    assert a["charger_mtbf_hours"] == cv.mtbf_hours
    assert a["charger_mttr_hours"] == cv.mttr_hours


def test_static_run_omits_stochastic_only_fields(static_run):
    """Phase-2-only fields should be None in static mode (omitted at render time)."""
    scenario, result, _cv, bundle = static_run
    data = _collect_report_data(scenario, result, bundle, mc_summary=None,
                                scenario_name="static", today=date(2026, 5, 7))

    rel = data["reliability"]
    assert rel["total_charger_failures"] is None
    assert rel["total_packs_retired"] is None
    assert rel["mean_soh_at_end"] is None
    assert rel["total_failure_to_serve"] is None
    assert data["monte_carlo"] is None


def test_pdf_renders_for_static_run_without_mc(static_run):
    scenario, result, _cv, bundle = static_run
    pdf = build_unit_economics_pdf(
        scenario, result, bundle,
        mc_summary=None, scenario_name="no-mc",
        today=date(2026, 5, 7),
    )
    assert pdf.startswith(b"%PDF-")
    # No Monte Carlo block present → smaller than a stochastic report would be
    assert len(pdf) > 1024
