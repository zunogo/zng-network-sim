"""Finance bundle — runs all Phase 3 modules for one charger variant.

Mirrors the inline ``_compute_finance`` helper inside ``dashboard/app.py``
so callers outside the Streamlit Finance tab (e.g. report generation)
can reuse the same computation without duplicating the wiring.
"""

from __future__ import annotations

from dataclasses import dataclass

from zng_simulator.config.charger import ChargerVariant
from zng_simulator.config.scenario import Scenario
from zng_simulator.finance.charger_npv import ChargerNPVResult, compute_charger_npv
from zng_simulator.finance.dcf import build_dcf_table
from zng_simulator.finance.dscr import build_debt_schedule, compute_dscr
from zng_simulator.finance.statements import build_financial_statements
from zng_simulator.models.results import (
    DCFResult,
    DebtSchedule,
    DSCRResult,
    FinancialStatements,
    SimulationResult,
)


@dataclass(frozen=True)
class FinanceBundle:
    """All Phase 3 finance outputs for one (result, variant) pair."""

    total_initial_capex: float
    total_salvage: float
    dcf: DCFResult
    debt: DebtSchedule
    dscr: DSCRResult
    statements: FinancialStatements
    charger_npv: ChargerNPVResult


def compute_finance_bundle(
    result: SimulationResult,
    charger_variant: ChargerVariant,
    scenario: Scenario,
) -> FinanceBundle:
    """Run DCF, debt, DSCR, statements, and charger NPV for one variant."""
    station = scenario.station
    pack = scenario.pack
    finance_cfg = scenario.finance
    opex_cfg = scenario.opex
    sim_cfg = scenario.simulation
    derived = result.derived

    per_station_capex = (
        station.cabinet_cost
        + station.site_prep_cost
        + station.grid_connection_cost
        + station.security_deposit
    )
    total_initial_capex = (
        per_station_capex * station.num_stations
        + station.software_cost
        + charger_variant.purchase_cost_per_slot * derived.total_docks
        + pack.unit_cost * derived.total_packs
    )
    total_salvage = derived.total_packs * pack.second_life_salvage_value

    dcf = build_dcf_table(
        result.months,
        result.summary,
        finance_cfg,
        sim_cfg.discount_rate_annual,
        total_salvage,
    )
    debt = build_debt_schedule(total_initial_capex, finance_cfg, sim_cfg.horizon_months)
    dscr = compute_dscr(result.months, debt, finance_cfg, total_salvage)
    statements = build_financial_statements(
        result.months,
        debt,
        finance_cfg,
        opex_cfg,
        station,
        pack,
        charger_variant,
        total_initial_capex,
    )
    charger_npv = compute_charger_npv(charger_variant, result.charger_tco, derived, sim_cfg, station)

    return FinanceBundle(
        total_initial_capex=total_initial_capex,
        total_salvage=total_salvage,
        dcf=dcf,
        debt=debt,
        dscr=dscr,
        statements=statements,
        charger_npv=charger_npv,
    )
