"""ZNG BSN Simulator — Phase 1 + Phase 2 + Phase 3 + Phase 4 Streamlit Dashboard.

Layout: sidebar inputs → main area with three tabs (Operations | Finance | Intelligence).
Design: metrics for headlines, proper tables, formulas in expanders,
restrained visualisations, dark polished card theme.
Phase 3 adds: Finance tab with DCF, debt schedule, DSCR, P&L, CF statement,
charger NPV comparison, and sensitivity/tornado analysis.
Phase 4 adds: Intelligence tab with pilot sizing optimizer, field data
ingestion, variance analysis, auto-tuning, and recommendation alerts.
"""

from __future__ import annotations

import io
import os
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from scipy.special import gamma as gamma_func

from zng_simulator.config import (
    ChaosConfig,
    ChargerVariant,
    DemandConfig,
    FinanceConfig,
    OpExConfig,
    PackSpec,
    RevenueConfig,
    Scenario,
    SimulationConfig,
    StationConfig,
    VehicleConfig,
)
from zng_simulator.engine.orchestrator import run_engine
from zng_simulator.engine.field_data import (
    apply_tuned_parameters,
    auto_tune_parameters,
    compute_variance_report,
    ingest_bms_csv,
    ingest_charger_csv,
)
from zng_simulator.engine.optimizer import find_minimum_fleet_size, find_optimal_scale
from zng_simulator.finance.dcf import build_dcf_table
from zng_simulator.finance.dscr import build_debt_schedule, compute_dscr
from zng_simulator.finance.statements import build_financial_statements
from zng_simulator.finance.charger_npv import compute_charger_npv
from zng_simulator.models.field_data import FieldDataSet
from zng_simulator.models.results import SimulationResult

# ---------------------------------------------------------------------------
# Default instances — single source of truth for sidebar defaults
# ---------------------------------------------------------------------------
_DEF_V = VehicleConfig()
_DEF_P = PackSpec()
_DEF_C = ChargerVariant()
_DEF_S = StationConfig()
_DEF_O = OpExConfig()
_DEF_R = RevenueConfig()
_DEF_CH = ChaosConfig()
_DEF_D = DemandConfig()
_DEF_F = FinanceConfig()
_DEF_SIM = SimulationConfig()

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(page_title="ZNG BSN Simulator", page_icon="⚡", layout="wide")

# ---------------------------------------------------------------------------
# Custom CSS — dark polished card theme
# ---------------------------------------------------------------------------
st.markdown("""
<style>
/* ── Google Fonts: Inter ─────────────────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

/* ── Global typography ───────────────────────────────────────────── */
html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
}

/* ── Metric cards ─────────────────────────────────────────────────── */
div[data-testid="stMetric"] {
    background: linear-gradient(135deg, rgba(30,34,44,0.95), rgba(22,26,35,0.98));
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 10px;
    padding: 14px 16px 12px;
    box-shadow: 0 1px 8px rgba(0,0,0,0.20);
}
div[data-testid="stMetric"] label {
    font-family: 'Inter', sans-serif !important;
    color: rgba(255,255,255,0.50) !important;
    font-size: 0.7rem !important;
    font-weight: 500 !important;
    text-transform: uppercase;
    letter-spacing: 0.6px;
    line-height: 1.4 !important;
}
div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
    font-family: 'Inter', sans-serif !important;
    font-size: 1.35rem !important;
    font-weight: 700 !important;
    letter-spacing: -0.3px;
    line-height: 1.3 !important;
}

/* ── Section headers ──────────────────────────────────────────────── */
h1 {
    font-family: 'Inter', sans-serif !important;
    font-size: 1.75rem !important;
    font-weight: 800 !important;
    letter-spacing: -0.5px;
    line-height: 1.2 !important;
}
h2 {
    font-family: 'Inter', sans-serif !important;
    font-size: 1.15rem !important;
    font-weight: 700 !important;
    border-left: 3px solid #6c5ce7;
    padding-left: 12px !important;
    margin-top: 0.75rem !important;
    margin-bottom: 0.5rem !important;
    letter-spacing: -0.2px;
    line-height: 1.3 !important;
}
h3 {
    font-family: 'Inter', sans-serif !important;
    color: rgba(255,255,255,0.70) !important;
    font-weight: 600 !important;
    font-size: 0.95rem !important;
    letter-spacing: 0;
    line-height: 1.3 !important;
    margin-top: 0.5rem !important;
    margin-bottom: 0.25rem !important;
}

/* ── Captions & small text ───────────────────────────────────────── */
div[data-testid="stCaptionContainer"] {
    font-size: 0.72rem !important;
    color: rgba(255,255,255,0.40) !important;
    line-height: 1.5 !important;
}

/* ── Expanders ────────────────────────────────────────────────────── */
details[data-testid="stExpander"] {
    background: rgba(30,34,44,0.5);
    border: 1px solid rgba(255,255,255,0.05);
    border-radius: 8px;
    margin-top: 4px !important;
    margin-bottom: 8px !important;
}
details[data-testid="stExpander"] summary span {
    font-family: 'Inter', sans-serif !important;
    font-size: 0.82rem !important;
    font-weight: 500 !important;
}

/* ── Dataframe containers ─────────────────────────────────────────── */
div[data-testid="stDataFrame"] {
    border-radius: 8px;
    overflow: hidden;
}

/* ── Tabs ─────────────────────────────────────────────────────────── */
button[data-baseweb="tab"] {
    font-family: 'Inter', sans-serif !important;
    font-weight: 600 !important;
    font-size: 0.85rem !important;
    letter-spacing: 0.2px;
    padding: 10px 20px !important;
}

/* ── Divider ──────────────────────────────────────────────────────── */
hr {
    border-color: rgba(255,255,255,0.05) !important;
    margin: 1.25rem 0 !important;
}

/* ── Sidebar polish ───────────────────────────────────────────────── */
section[data-testid="stSidebar"] > div {
    padding-top: 1rem;
}
section[data-testid="stSidebar"] h1 {
    font-size: 0.85rem !important;
    font-weight: 700 !important;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    color: rgba(255,255,255,0.55) !important;
}
section[data-testid="stSidebar"] details summary span {
    font-size: 0.78rem !important;
    font-weight: 600 !important;
}
section[data-testid="stSidebar"] label {
    font-size: 0.75rem !important;
    font-weight: 500 !important;
}
section[data-testid="stSidebar"] .stButton button {
    font-family: 'Inter', sans-serif !important;
    font-weight: 600 !important;
    font-size: 0.85rem !important;
    letter-spacing: 0.2px;
}

/* ── Alert banners ────────────────────────────────────────────────── */
div[data-testid="stAlert"] p {
    font-size: 0.82rem !important;
    line-height: 1.5 !important;
}

/* ── Buttons ──────────────────────────────────────────────────────── */
.stButton button {
    font-family: 'Inter', sans-serif !important;
    font-weight: 600 !important;
    font-size: 0.82rem !important;
    letter-spacing: 0.2px;
    border-radius: 8px !important;
}

/* ── File uploader ────────────────────────────────────────────────── */
section[data-testid="stFileUploader"] label {
    font-size: 0.78rem !important;
}

/* ── Download button ──────────────────────────────────────────────── */
.stDownloadButton button {
    font-size: 0.78rem !important;
    border-radius: 8px !important;
}
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Title area — Zunogo branding
# ---------------------------------------------------------------------------
_logo_path = Path(__file__).parent / "assets" / "zunogo_logo.png"
_logo_path_svg = Path(__file__).parent / "assets" / "zunogo_logo.svg"

# Try to find logo file (PNG or SVG)
_logo_file = None
if _logo_path.exists():
    _logo_file = str(_logo_path)
elif _logo_path_svg.exists():
    _logo_file = str(_logo_path_svg)

if _logo_file:
    col_logo, col_title = st.columns([0.12, 0.88])
    with col_logo:
        st.image(_logo_file, width=36)
    with col_title:
        st.markdown("""
        <div style="margin-top: 4px;">
            <div style="font-family: 'Inter', sans-serif; font-size: 1.5rem; font-weight: 800; letter-spacing: -0.8px; color: #fff; line-height: 1.2;">
                ZNG Battery Swap Network Simulator
            </div>
            <div style="font-family: 'Inter', sans-serif; font-size: 0.7rem; font-weight: 500; color: rgba(255,255,255,0.38); letter-spacing: 1.2px; text-transform: uppercase; margin-top: 2px;">
                Digital Twin &amp; Financial Simulator
            </div>
        </div>
        """, unsafe_allow_html=True)
else:
    # Fallback if logo not found
    st.markdown("""
    <div style="margin-bottom: 4px;">
        <div style="font-family: 'Inter', sans-serif; font-size: 1.5rem; font-weight: 800; letter-spacing: -0.8px; color: #fff; line-height: 1.2;">
            ZNG Battery Swap Network Simulator
        </div>
        <div style="font-family: 'Inter', sans-serif; font-size: 0.7rem; font-weight: 500; color: rgba(255,255,255,0.38); letter-spacing: 1.2px; text-transform: uppercase; margin-top: 2px;">
            Digital Twin &amp; Financial Simulator
        </div>
    </div>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fmt_inr(val: float) -> str:
    """Format INR with lakhs / crores for large values."""
    if abs(val) >= 1e7:
        return f"₹{val / 1e7:,.2f} Cr"
    if abs(val) >= 1e5:
        return f"₹{val / 1e5:,.2f} L"
    return f"₹{val:,.0f}"


def _card(icon: str, label: str, value: str, accent: str = "#6c5ce7") -> str:
    """Return HTML for a styled metric card with colored top accent."""
    return f"""
    <div style="
        background: linear-gradient(135deg, rgba(30,34,44,0.95), rgba(22,26,35,0.98));
        border: 1px solid rgba(255,255,255,0.05);
        border-top: 3px solid {accent};
        border-radius: 8px;
        padding: 14px 16px 12px;
        box-shadow: 0 1px 6px rgba(0,0,0,0.18);
        text-align: center;
    ">
        <div style="font-size: 1.3rem; margin-bottom: 2px; line-height: 1;">{icon}</div>
        <div style="font-family: 'Inter', sans-serif; font-size: 1.25rem; font-weight: 700; color: #fff; letter-spacing: -0.3px; line-height: 1.3;">{value}</div>
        <div style="font-family: 'Inter', sans-serif; font-size: 0.65rem; color: rgba(255,255,255,0.42); text-transform: uppercase; letter-spacing: 0.6px; margin-top: 3px; line-height: 1.3; font-weight: 500;">{label}</div>
    </div>
    """


# ---------------------------------------------------------------------------
# SIDEBAR — Inputs
# ---------------------------------------------------------------------------
st.sidebar.header("Scenario Inputs")

# --- Simulation (define sim_engine first, needed by other sections) ---
with st.sidebar.expander("Simulation", expanded=True):
    sim_horizon = st.number_input("Horizon months", 6, 240, _DEF_SIM.horizon_months, 12)
    _ENGINES = ["static", "stochastic"]
    sim_engine = st.selectbox("Engine", _ENGINES, index=_ENGINES.index(_DEF_SIM.engine),
                              help="Static = Phase 1 deterministic · Stochastic = Phase 2 with noise, degradation cohorts, charger failures")
    c1, c2 = st.columns(2)
    sim_mc = c1.number_input("MC runs", 1, 5000, _DEF_SIM.monte_carlo_runs if sim_engine == "stochastic" else 1,
                             disabled=(sim_engine == "static"),
                             help="Number of Monte-Carlo iterations (stochastic only)")
    sim_seed = c2.number_input("Seed", 0, 999999, 42,
                               disabled=(sim_engine == "static"),
                               help="Random seed for reproducibility")

# --- Vehicle ---
with st.sidebar.expander("Vehicle", expanded=True):
    v_name = st.text_input("Vehicle name", _DEF_V.name)
    c1, c2 = st.columns(2)
    v_packs = c1.number_input("Packs per vehicle", 1, 4, _DEF_V.packs_per_vehicle)
    v_cap = c2.number_input("Pack capacity kWh", 0.1, 10.0, _DEF_V.pack_capacity_kwh, 0.01, format="%.2f")
    c1, c2 = st.columns(2)
    v_km = c1.number_input("Daily km", 1.0, 500.0, _DEF_V.avg_daily_km, 10.0)
    v_wh = c2.number_input("Wh per km", 1.0, 100.0, _DEF_V.energy_consumption_wh_per_km, 1.0)
    c1, c2 = st.columns(2)
    v_swap = c1.number_input("Swap time min", 0.5, 10.0, _DEF_V.swap_time_minutes, 0.5)
    v_buffer = c2.number_input("Range buffer %", 0, 50, int(_DEF_V.range_anxiety_buffer_pct * 100), 5)

vehicle = VehicleConfig(
    name=v_name, packs_per_vehicle=v_packs, pack_capacity_kwh=v_cap,
    avg_daily_km=v_km, energy_consumption_wh_per_km=v_wh,
    swap_time_minutes=v_swap, range_anxiety_buffer_pct=v_buffer / 100,
)

# --- Pack ---
_CHEM_OPTIONS = ["NMC", "LFP"]
with st.sidebar.expander("Battery Pack"):
    p_name = st.text_input("Pack name", _DEF_P.name)
    c1, c2 = st.columns(2)
    p_cap = c1.number_input("Capacity kWh", 0.1, 10.0, _DEF_P.nominal_capacity_kwh, 0.01, format="%.2f", key="p_cap")
    p_chem = c2.selectbox("Chemistry", _CHEM_OPTIONS, index=_CHEM_OPTIONS.index(_DEF_P.chemistry) if _DEF_P.chemistry in _CHEM_OPTIONS else 0)
    c1, c2 = st.columns(2)
    p_cost = c1.number_input("Unit cost ₹", 0, 200000, int(_DEF_P.unit_cost), 1000)
    p_salvage = c2.number_input("Salvage ₹", 0, 100000, int(_DEF_P.second_life_salvage_value), 500)
    c1, c2 = st.columns(2)
    p_beta = c1.number_input("β %/cycle", 0.001, 1.0, _DEF_P.cycle_degradation_rate_pct, 0.01, format="%.3f")
    p_retire = c2.number_input("Retire SOH %", 10, 100, int(_DEF_P.retirement_soh_pct * 100), 5)
    c1, c2 = st.columns(2)
    p_dod = c1.number_input("DoD %", 10, 100, int(_DEF_P.depth_of_discharge_pct * 100), 5)
    p_aggr = c2.number_input("Aggressiveness", 0.1, 3.0, _DEF_P.aggressiveness_multiplier, 0.1)
    st.markdown("---\n**Pack Failure Model**")
    c1, c2 = st.columns(2)
    p_mtbf = c1.number_input("MTBF hrs", 1000, 500000, int(_DEF_P.mtbf_hours), 1000, key="p_mtbf")
    p_mttr = c2.number_input("MTTR hrs", 1, 200, int(_DEF_P.mttr_hours), 1, key="p_mttr")
    c1, c2 = st.columns(2)
    p_repair = c1.number_input("Repair ₹", 0, 50000, int(_DEF_P.repair_cost_per_event), 500, key="p_repair")
    p_thresh = c2.number_input("Replace after", 1, 10, _DEF_P.replacement_threshold, 1, key="p_thresh")
    c1, c2 = st.columns(2)
    p_repl = c1.number_input("Replace ₹", 0, 200000, int(_DEF_P.full_replacement_cost), 1000, key="p_repl")
    p_spare = c2.number_input("Spare/stn ₹", 0, 200000, int(_DEF_P.spare_packs_cost_per_station), 1000, key="p_spare")
    
    # Preview button for pack failures
    if sim_engine == "stochastic":
        show_pack_failure_preview = st.checkbox("Show failure distribution", value=False, key="pack_failure_preview")
    else:
        show_pack_failure_preview = False

pack = PackSpec(
    name=p_name, nominal_capacity_kwh=p_cap, chemistry=p_chem, unit_cost=float(p_cost),
    cycle_life_to_retirement=_DEF_P.cycle_life_to_retirement, cycle_degradation_rate_pct=p_beta,
    calendar_aging_rate_pct_per_month=_DEF_P.calendar_aging_rate_pct_per_month,
    depth_of_discharge_pct=p_dod / 100,
    retirement_soh_pct=p_retire / 100, second_life_salvage_value=float(p_salvage),
    weight_kg=_DEF_P.weight_kg, aggressiveness_multiplier=p_aggr,
    mtbf_hours=float(p_mtbf), mttr_hours=float(p_mttr),
    repair_cost_per_event=float(p_repair), replacement_threshold=p_thresh,
    full_replacement_cost=float(p_repl), spare_packs_cost_per_station=float(p_spare),
)

# --- Chargers ---
with st.sidebar.expander("Charger Variants"):
    num_chargers = st.number_input("Variants to compare", 1, 5, 1)
    charger_variants: list[ChargerVariant] = []
    charger_preview_flags: list[bool] = []
    charger_preview_params: list[dict] = []
    for i in range(num_chargers):
        st.markdown(f"---\n**Charger {i + 1}**")
        c_name = st.text_input("Name", f"Charger-{i+1}", key=f"cn_{i}")
        c1, c2 = st.columns(2)
        c_cost = c1.number_input("Cost per slot ₹", 0, 200000, int(_DEF_C.purchase_cost_per_slot), 1000, key=f"cc_{i}")
        c_power = c2.number_input("Rated power W", 100, 10000, int(_DEF_C.rated_power_w), 100, key=f"cp_{i}")
        c1, c2 = st.columns(2)
        c_eff = c1.number_input("Efficiency %", 50, 100, int(_DEF_C.charging_efficiency_pct * 100), 1, key=f"ce_{i}")
        c_mtbf = c2.number_input("MTBF hrs", 1000, 200000, int(_DEF_C.mtbf_hours), 1000, key=f"cm_{i}")
        c1, c2 = st.columns(2)
        c_mttr = c1.number_input("MTTR hrs", 1, 200, int(_DEF_C.mttr_hours), 4, key=f"cmt_{i}")
        c_repair = c2.number_input("Repair cost ₹", 0, 50000, int(_DEF_C.repair_cost_per_event), 500, key=f"cr_{i}")
        c1, c2 = st.columns(2)
        c_thresh = c1.number_input("Replace after #", 1, 10, _DEF_C.replacement_threshold, 1, key=f"ct_{i}")
        c_repl = c2.number_input("Replace cost ₹", 0, 200000, int(_DEF_C.full_replacement_cost), 1000, key=f"crc_{i}")
        c_spare = st.number_input("Spare inventory ₹", 0, 200000, int(_DEF_C.spare_inventory_cost), 1000, key=f"cs_{i}")
        st.markdown("**Failure Model**")
        _FAIL_DIST = ["exponential", "weibull"]
        c_fdist = st.selectbox("Distribution", _FAIL_DIST,
                               index=_FAIL_DIST.index(_DEF_C.failure_distribution), key=f"cfd_{i}")
        c_wshape = st.number_input("Weibull β", 0.1, 5.0, _DEF_C.weibull_shape, 0.1, key=f"cwb_{i}",
                                   help="Shape: β<1 infant mortality, β=1 exponential, β>1 wear-out",
                                   disabled=(c_fdist != "weibull"))
        
        # Preview button for charger failures
        if sim_engine == "stochastic":
            show_preview = st.checkbox("Show failure distribution", value=False, key=f"charger_failure_preview_{i}")
            charger_preview_flags.append(show_preview)
            charger_preview_params.append({
                "name": c_name,
                "mtbf": float(c_mtbf),
                "mttr": float(c_mttr),
                "distribution": c_fdist,
                "weibull_shape": c_wshape if c_fdist == "weibull" else 1.0,
            })
        else:
            charger_preview_flags.append(False)
            charger_preview_params.append({})
        
        charger_variants.append(ChargerVariant(
            name=c_name, purchase_cost_per_slot=float(c_cost), rated_power_w=float(c_power),
            charging_efficiency_pct=c_eff / 100,
            efficiency_decay_pct_per_year=_DEF_C.efficiency_decay_pct_per_year,
            mtbf_hours=float(c_mtbf), mttr_hours=float(c_mttr),
            repair_cost_per_event=float(c_repair), replacement_threshold=c_thresh,
            full_replacement_cost=float(c_repl), spare_inventory_cost=float(c_spare),
            expected_useful_life_years=_DEF_C.expected_useful_life_years,
            failure_distribution=c_fdist,
            weibull_shape=c_wshape if c_fdist == "weibull" else 1.0,
        ))

# --- Station ---
with st.sidebar.expander("Station & Infrastructure"):
    c1, c2 = st.columns(2)
    s_num = c1.number_input("Stations", 1, 100, _DEF_S.num_stations, 1)
    s_docks = c2.number_input("Docks per stn", 1, 50, _DEF_S.docks_per_station, 1)
    s_hours = st.number_input("Operating hrs/day", 1.0, 24.0, _DEF_S.operating_hours_per_day, 1.0)
    c1, c2 = st.columns(2)
    s_cab = c1.number_input("Cabinet cost ₹", 0, 500000, int(_DEF_S.cabinet_cost), 5000)
    s_site = c2.number_input("Site prep ₹", 0, 500000, int(_DEF_S.site_prep_cost), 5000)
    c1, c2 = st.columns(2)
    s_grid = c1.number_input("Grid connection ₹", 0, 500000, int(_DEF_S.grid_connection_cost), 5000)
    s_sw = c2.number_input("Software ₹", 0, 1000000, int(_DEF_S.software_cost), 10000)
    s_dep = st.number_input("Security deposit ₹", 0, 500000, int(_DEF_S.security_deposit), 5000)

station = StationConfig(
    cabinet_cost=float(s_cab), site_prep_cost=float(s_site), grid_connection_cost=float(s_grid),
    software_cost=float(s_sw), security_deposit=float(s_dep), num_stations=s_num,
    docks_per_station=s_docks, operating_hours_per_day=s_hours,
)

# --- OpEx ---
with st.sidebar.expander("Operating Expenses"):
    o_tariff = st.number_input("Electricity ₹/kWh", 0.0, 30.0, _DEF_O.electricity_tariff_per_kwh, 0.5)
    c1, c2 = st.columns(2)
    o_rent = c1.number_input("Rent ₹/mo/stn", 0, 200000, int(_DEF_O.rent_per_month_per_station), 1000)
    o_aux = c2.number_input("Aux power ₹/mo", 0, 50000, int(_DEF_O.auxiliary_power_per_month), 500)
    c1, c2 = st.columns(2)
    o_prev = c1.number_input("Preventive maint ₹", 0, 50000, int(_DEF_O.preventive_maintenance_per_month_per_station), 500)
    o_corr = c2.number_input("Corrective maint ₹", 0, 50000, int(_DEF_O.corrective_maintenance_per_month_per_station), 500)
    c1, c2 = st.columns(2)
    o_ins = c1.number_input("Insurance ₹/mo", 0, 50000, int(_DEF_O.insurance_per_month_per_station), 500)
    o_log = c2.number_input("Logistics ₹/mo", 0, 50000, int(_DEF_O.logistics_per_month_per_station), 1000)
    c1, c2 = st.columns(2)
    o_labor = c1.number_input("Labor ₹/swap", 0.0, 50.0, _DEF_O.pack_handling_labor_per_swap, 0.5)
    o_overhead = c2.number_input("Overhead ₹/mo", 0, 500000, int(_DEF_O.overhead_per_month), 5000)

opex_cfg = OpExConfig(
    electricity_tariff_per_kwh=o_tariff, auxiliary_power_per_month=float(o_aux),
    rent_per_month_per_station=float(o_rent),
    preventive_maintenance_per_month_per_station=float(o_prev),
    corrective_maintenance_per_month_per_station=float(o_corr),
    insurance_per_month_per_station=float(o_ins),
    logistics_per_month_per_station=float(o_log),
    pack_handling_labor_per_swap=o_labor, overhead_per_month=float(o_overhead),
)

# --- Revenue ---
with st.sidebar.expander("Revenue"):
    r_price = st.number_input("Price per swap ₹", 0.0, 200.0, _DEF_R.price_per_swap, 5.0, help="Per vehicle visit, not per pack")
    c1, c2 = st.columns(2)
    r_fleet = c1.number_input("Initial fleet", 1, 100000, _DEF_R.initial_fleet_size, 50)
    r_add = c2.number_input("Monthly additions", 0, 5000, _DEF_R.monthly_fleet_additions, 10)

revenue_cfg = RevenueConfig(price_per_swap=r_price, initial_fleet_size=r_fleet, monthly_fleet_additions=r_add)

# --- Chaos ---
with st.sidebar.expander("Risk Factors"):
    c1, c2 = st.columns(2)
    ch_sab = c1.number_input("Sabotage %/mo", 0.0, 10.0, _DEF_CH.sabotage_pct_per_month * 100, 0.1, format="%.1f")
    ch_aggr = c2.number_input("Aggressiveness", 0.1, 3.0, _DEF_CH.aggressiveness_index, 0.1, key="ch_aggr")

chaos_cfg = ChaosConfig(sabotage_pct_per_month=ch_sab / 100, aggressiveness_index=ch_aggr, thermal_throttling_factor=1.0)

# --- Finance (Phase 3) ---
with st.sidebar.expander("Finance"):
    c1, c2 = st.columns(2)
    f_debt_pct = c1.number_input("Debt % of CapEx", 0, 100, int(_DEF_F.debt_pct_of_capex * 100), 5, key="f_debt")
    f_rate = c2.number_input("Interest rate %", 0.0, 50.0, _DEF_F.interest_rate_annual * 100, 0.5, key="f_rate", format="%.1f")
    c1, c2 = st.columns(2)
    f_tenor = c1.number_input("Loan tenor mo", 12, 360, _DEF_F.loan_tenor_months, 12, key="f_tenor")
    f_grace = c2.number_input("Grace period mo", 0, 60, _DEF_F.grace_period_months, 3, key="f_grace")
    c1, c2 = st.columns(2)
    _DEPR_OPTS = ["straight_line", "wdv"]
    f_depr = c1.selectbox("Depreciation", _DEPR_OPTS, index=_DEPR_OPTS.index(_DEF_F.depreciation_method), key="f_depr")
    f_life = c2.number_input("Asset life mo", 12, 360, _DEF_F.asset_useful_life_months, 12, key="f_life")
    c1, c2 = st.columns(2)
    f_tax = c1.number_input("Tax rate %", 0, 60, int(_DEF_F.tax_rate * 100), 1, key="f_tax")
    f_wdv = c2.number_input("WDV rate %", 0, 100, int(_DEF_F.wdv_rate_annual * 100), 5, key="f_wdv",
                            disabled=(f_depr != "wdv"))
    _TV_OPTS = ["salvage", "gordon_growth", "none"]
    f_tv = st.selectbox("Terminal value", _TV_OPTS, index=_TV_OPTS.index(_DEF_F.terminal_value_method), key="f_tv")
    c1, c2 = st.columns(2)
    f_tg = c1.number_input("Growth rate %", 0.0, 10.0, _DEF_F.terminal_growth_rate * 100, 0.5, key="f_tg",
                           disabled=(f_tv != "gordon_growth"))
    f_dscr = c2.number_input("DSCR covenant", 0.5, 3.0, _DEF_F.dscr_covenant_threshold, 0.1, key="f_dscr")

finance_cfg = FinanceConfig(
    debt_pct_of_capex=f_debt_pct / 100,
    interest_rate_annual=f_rate / 100,
    loan_tenor_months=f_tenor,
    grace_period_months=f_grace,
    depreciation_method=f_depr,
    asset_useful_life_months=f_life,
    wdv_rate_annual=f_wdv / 100,
    tax_rate=f_tax / 100,
    terminal_value_method=f_tv,
    terminal_growth_rate=f_tg / 100,
    dscr_covenant_threshold=f_dscr,
)

# --- Demand model (Phase 2) ---
with st.sidebar.expander("Demand Model", expanded=(sim_engine == "stochastic")):
    st.markdown("**Distribution Type**")
    _DEMAND_DIST = ["poisson", "gamma", "bimodal"]
    d_dist = st.selectbox("Distribution", _DEMAND_DIST, 
                          index=_DEMAND_DIST.index(_DEF_D.distribution) if _DEF_D.distribution in _DEMAND_DIST else 0,
                          disabled=(sim_engine == "static"),
                          help="Poisson: simple count data | Gamma: heavier tails | Bimodal: dual-peak patterns")
    
    st.markdown("**Daily Variability**")
    if d_dist == "gamma":
        d_vol = st.slider("Volatility (CoV)", 0.0, 2.0, _DEF_D.volatility, 0.01,
                          disabled=(sim_engine == "static"),
                          help="Coefficient of Variation (σ/μ). 0.15 = mild, 0.3 = moderate, 0.5+ = high variability")
    elif d_dist == "bimodal":
        d_vol = _DEF_D.volatility  # Not used for bimodal
        c1, c2 = st.columns(2)
        d_bimodal_ratio = c1.slider("Peak 1 weight", 0.1, 0.9, _DEF_D.bimodal_peak_ratio, 0.05,
                                     disabled=(sim_engine == "static"),
                                     help="Relative weight of first peak")
        d_bimodal_sep = c2.slider("Peak separation", 0.1, 2.0, _DEF_D.bimodal_peak_separation, 0.1,
                                   disabled=(sim_engine == "static"),
                                   help="Distance between peaks (× mean)")
        d_bimodal_std = st.slider("Peak width", 0.05, 0.5, _DEF_D.bimodal_std_ratio, 0.05,
                                   disabled=(sim_engine == "static"),
                                   help="Standard deviation of each peak (× mean)")
    else:  # poisson
        d_vol = _DEF_D.volatility
        d_bimodal_ratio = _DEF_D.bimodal_peak_ratio
        d_bimodal_sep = _DEF_D.bimodal_peak_separation
        d_bimodal_std = _DEF_D.bimodal_std_ratio
        st.caption("Poisson distribution has fixed CoV = 1/√λ")
    
    st.markdown("**Temporal Patterns**")
    c1, c2 = st.columns(2)
    d_wknd = c1.number_input("Weekend factor", 0.0, 2.0, _DEF_D.weekend_factor, 0.05,
                             disabled=(sim_engine == "static"),
                             help="Demand multiplier for Sat/Sun")
    d_season = c2.number_input("Seasonal amplitude", 0.0, 1.0, _DEF_D.seasonal_amplitude, 0.05,
                               disabled=(sim_engine == "static"),
                               help="Peak-to-trough amplitude")
    
    # Preview button
    if sim_engine == "stochastic":
        show_demand_preview = st.checkbox("Show demand preview", value=False, key="demand_preview_check")
    else:
        show_demand_preview = False

demand_cfg = DemandConfig(
    distribution=d_dist, volatility=d_vol,
    weekend_factor=d_wknd, seasonal_amplitude=d_season,
    bimodal_peak_ratio=d_bimodal_ratio if d_dist == "bimodal" else _DEF_D.bimodal_peak_ratio,
    bimodal_peak_separation=d_bimodal_sep if d_dist == "bimodal" else _DEF_D.bimodal_peak_separation,
    bimodal_std_ratio=d_bimodal_std if d_dist == "bimodal" else _DEF_D.bimodal_std_ratio,
)

sim_cfg = SimulationConfig(
    horizon_months=sim_horizon, discount_rate_annual=_DEF_SIM.discount_rate_annual,
    engine=sim_engine,
    random_seed=sim_seed if sim_engine == "stochastic" else None,
    monte_carlo_runs=sim_mc if sim_engine == "stochastic" else 1,
)

# --- Build scenario & run ---
scenario = Scenario(
    vehicle=vehicle, pack=pack, charger_variants=charger_variants,
    station=station, opex=opex_cfg, revenue=revenue_cfg, chaos=chaos_cfg,
    demand=demand_cfg, finance=finance_cfg, simulation=sim_cfg,
)

run_clicked = st.sidebar.button("Run Simulation", type="primary", use_container_width=True)

# ---------------------------------------------------------------------------
# Demand Model Preview (if enabled)
# ---------------------------------------------------------------------------
if show_demand_preview and sim_engine == "stochastic":
    st.markdown("---")
    st.subheader("Demand Model Preview")
    st.caption("Visual preview of the configured demand distribution and temporal patterns")
    
    # Calculate base demand rate
    base_daily_km = vehicle.avg_daily_km
    base_wh_per_km = vehicle.energy_consumption_wh_per_km
    base_pack_cap_wh = vehicle.pack_capacity_kwh * 1000
    base_buffer = vehicle.range_anxiety_buffer_pct
    base_energy_per_swap = base_pack_cap_wh * (1 - base_buffer)
    base_swaps_per_day = (base_daily_km * base_wh_per_km) / base_energy_per_swap
    
    # Distribution visualization
    col_dist, col_temporal = st.columns(2)
    
    with col_dist:
        st.markdown("**Daily Demand Distribution**")
        
        # Generate samples
        n_samples = 1000
        if d_dist == "poisson":
            lam = max(0.1, base_swaps_per_day)
            samples = np.random.poisson(lam, n_samples)
            theoretical_mean = lam
            theoretical_std = np.sqrt(lam)
        elif d_dist == "gamma":
            mean = max(0.1, base_swaps_per_day)
            cv = d_vol
            if cv > 0:
                shape = 1 / (cv ** 2)
                scale = mean * (cv ** 2)
                samples = np.random.gamma(shape, scale, n_samples)
            else:
                samples = np.full(n_samples, mean)
            theoretical_mean = mean
            theoretical_std = mean * cv
        else:  # bimodal
            mean = max(0.1, base_swaps_per_day)
            w1 = demand_cfg.bimodal_peak_ratio
            w2 = 1.0 - w1
            sep = demand_cfg.bimodal_peak_separation
            std_ratio = demand_cfg.bimodal_std_ratio
            
            # Peak positions
            mu1 = mean - w2 * sep * mean
            mu2 = mean + w1 * sep * mean
            sigma = std_ratio * mean
            
            # Sample from mixture
            samples = np.zeros(n_samples)
            for i in range(n_samples):
                if np.random.random() < w1:
                    samples[i] = np.random.normal(mu1, sigma)
                else:
                    samples[i] = np.random.normal(mu2, sigma)
            samples = np.maximum(samples, 0)  # Ensure non-negative
            
            theoretical_mean = mean
            theoretical_std = np.sqrt(w1 * (sigma**2 + (mu1 - mean)**2) + 
                                     w2 * (sigma**2 + (mu2 - mean)**2))
        
        # Create histogram
        fig_dist = go.Figure()
        fig_dist.add_trace(go.Histogram(
            x=samples,
            nbinsx=30,
            name="Simulated",
            marker_color="#6c5ce7",
            opacity=0.7,
        ))
        fig_dist.add_vline(x=theoretical_mean, line_dash="dash", line_color="#00b894",
                          annotation_text=f"Mean: {theoretical_mean:.2f}",
                          annotation_position="top right")
        fig_dist.update_layout(
            xaxis_title="Swaps per Vehicle per Day",
            yaxis_title="Frequency",
            height=280,
            margin=dict(l=20, r=20, t=30, b=20),
            showlegend=False,
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font=dict(family="Inter", size=11, color="rgba(255,255,255,0.7)"),
        )
        st.plotly_chart(fig_dist, use_container_width=True)
        
        # Stats
        st.markdown(f"""
        <div style="font-family: 'Inter', sans-serif; font-size: 0.75rem; color: rgba(255,255,255,0.5); line-height: 1.6;">
        <b>Distribution:</b> {d_dist.title()}<br>
        <b>Mean:</b> {theoretical_mean:.3f} swaps/day<br>
        <b>Std Dev:</b> {theoretical_std:.3f}<br>
        <b>CoV:</b> {theoretical_std/theoretical_mean:.3f}
        </div>
        """, unsafe_allow_html=True)
    
    with col_temporal:
        st.markdown("**Temporal Patterns (90 days)**")
        
        # Generate 90-day pattern
        days = 90
        day_nums = np.arange(days)
        
        # Base demand
        daily_demand = np.full(days, base_swaps_per_day)
        
        # Apply weekend factor
        is_weekend = (day_nums % 7 >= 5)  # Assuming day 0 is Monday
        daily_demand[is_weekend] *= d_wknd
        
        # Apply seasonal pattern
        if d_season > 0:
            seasonal_factor = 1 + d_season * np.sin(2 * np.pi * day_nums / 365)
            daily_demand *= seasonal_factor
        
        # Create time series plot
        fig_temporal = go.Figure()
        fig_temporal.add_trace(go.Scatter(
            x=day_nums,
            y=daily_demand,
            mode='lines',
            name='Expected Demand',
            line=dict(color='#0984e3', width=2),
            fill='tozeroy',
            fillcolor='rgba(9,132,227,0.2)',
        ))
        
        # Add weekend shading
        for i in range(0, days, 7):
            fig_temporal.add_vrect(
                x0=i+5, x1=i+7,
                fillcolor="rgba(255,255,255,0.03)",
                layer="below",
                line_width=0,
            )
        
        fig_temporal.update_layout(
            xaxis_title="Day",
            yaxis_title="Swaps per Vehicle",
            height=280,
            margin=dict(l=20, r=20, t=30, b=20),
            showlegend=False,
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font=dict(family="Inter", size=11, color="rgba(255,255,255,0.7)"),
        )
        st.plotly_chart(fig_temporal, use_container_width=True)
        
        # Pattern summary
        weekday_avg = daily_demand[~is_weekend].mean()
        weekend_avg = daily_demand[is_weekend].mean()
        overall_avg = daily_demand.mean()
        
        st.markdown(f"""
        <div style="font-family: 'Inter', sans-serif; font-size: 0.75rem; color: rgba(255,255,255,0.5); line-height: 1.6;">
        <b>Weekday avg:</b> {weekday_avg:.3f} swaps/day<br>
        <b>Weekend avg:</b> {weekend_avg:.3f} swaps/day<br>
        <b>Overall avg:</b> {overall_avg:.3f} swaps/day<br>
        <b>Peak/trough ratio:</b> {daily_demand.max()/daily_demand.min():.2f}×
        </div>
        """, unsafe_allow_html=True)
    
    # Key insights
    with st.expander("Understanding the demand model"):
        st.markdown("""
        **Distribution Types:**
        - **Poisson**: Natural choice for count data (number of swaps). Variance equals mean. Good for modeling independent events.
        - **Gamma**: More flexible, allows higher variance. Better for modeling aggregated demand or when demand has "memory" effects.
        - **Bimodal**: Mixture of two Gaussian peaks. Ideal for capturing dual-peak patterns like:
          - Morning/evening commute rushes
          - Personal vs commercial user segments
          - Different vehicle types with distinct usage patterns
        
        **For Gamma — Volatility (CoV):**
        - Coefficient of Variation = σ/μ (standard deviation ÷ mean)
        - 0.0–0.15: Low variability, predictable demand
        - 0.15–0.3: Moderate variability, typical for urban mobility
        - 0.3+: High variability, unpredictable demand patterns
        
        **For Bimodal — Parameters:**
        - **Peak 1 weight**: Proportion of demand from first peak (e.g., 0.6 = 60% morning, 40% evening)
        - **Peak separation**: Distance between peaks in units of mean demand (0.5 = peaks are 50% of mean apart)
        - **Peak width**: Standard deviation of each peak (0.15 = each peak has σ = 15% of mean)
        
        **Temporal Patterns:**
        - **Weekend factor**: Captures weekly patterns (e.g., lower commercial usage on weekends)
        - **Seasonal amplitude**: Captures annual patterns (e.g., monsoon season, festivals, temperature effects)
        
        **Why this matters:**
        - Higher volatility → need more buffer capacity (packs, docks)
        - Weekend/seasonal patterns → optimize staffing and maintenance schedules
        - Monte Carlo simulations use these distributions to generate realistic demand scenarios
        """)
    
    st.markdown("---")

# ---------------------------------------------------------------------------
# Pack Failure Model Preview (if enabled)
# ---------------------------------------------------------------------------
if show_pack_failure_preview and sim_engine == "stochastic":
    st.markdown("---")
    st.subheader("Pack Failure Model Preview")
    st.caption("Exponential failure distribution (constant hazard rate)")
    
    # Parameters
    mtbf_hrs = p_mtbf
    mttr_hrs = p_mttr
    
    # Time range (in hours) - show 3x MTBF
    t_max = mtbf_hrs * 3
    t = np.linspace(0, t_max, 500)
    
    # Exponential distribution: λ = 1/MTBF
    lam = 1.0 / mtbf_hrs
    
    # PDF: probability density function
    pdf = lam * np.exp(-lam * t)
    
    # CDF: cumulative distribution (probability of failure by time t)
    cdf = 1 - np.exp(-lam * t)
    
    # Reliability function (1 - CDF)
    reliability = np.exp(-lam * t)
    
    # Hazard rate (constant for exponential)
    hazard_rate = np.full_like(t, lam)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Failure Probability**")
        fig_pdf = go.Figure()
        fig_pdf.add_trace(go.Scatter(
            x=t / 1000,  # Convert to thousands of hours
            y=pdf * 1000,  # Scale for readability
            mode='lines',
            name='PDF',
            line=dict(color='#e74c3c', width=2),
            fill='tozeroy',
            fillcolor='rgba(231,76,60,0.2)',
        ))
        fig_pdf.add_vline(x=mtbf_hrs / 1000, line_dash="dash", line_color="#00b894",
                         annotation_text=f"MTBF: {mtbf_hrs/1000:.1f}k hrs",
                         annotation_position="top right")
        fig_pdf.update_layout(
            xaxis_title="Time (k hours)",
            yaxis_title="Probability Density (×10³)",
            height=280,
            margin=dict(l=20, r=20, t=30, b=20),
            showlegend=False,
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font=dict(family="Inter", size=11, color="rgba(255,255,255,0.7)"),
        )
        st.plotly_chart(fig_pdf, use_container_width=True)
        
        st.markdown(f"""
        <div style="font-family: 'Inter', sans-serif; font-size: 0.75rem; color: rgba(255,255,255,0.5); line-height: 1.6;">
        <b>MTBF:</b> {mtbf_hrs:,.0f} hours<br>
        <b>MTTR:</b> {mttr_hrs:.1f} hours<br>
        <b>Availability:</b> {100 * mtbf_hrs / (mtbf_hrs + mttr_hrs):.2f}%
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("**Reliability Over Time**")
        fig_rel = go.Figure()
        fig_rel.add_trace(go.Scatter(
            x=t / 1000,
            y=reliability * 100,
            mode='lines',
            name='Reliability',
            line=dict(color='#00b894', width=2),
            fill='tozeroy',
            fillcolor='rgba(0,184,148,0.2)',
        ))
        # Add horizontal line at 50% reliability
        fig_rel.add_hline(y=50, line_dash="dot", line_color="rgba(255,255,255,0.3)",
                         annotation_text="50% survival",
                         annotation_position="bottom right")
        fig_rel.update_layout(
            xaxis_title="Time (k hours)",
            yaxis_title="Probability Still Working (%)",
            height=280,
            margin=dict(l=20, r=20, t=30, b=20),
            showlegend=False,
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font=dict(family="Inter", size=11, color="rgba(255,255,255,0.7)"),
        )
        st.plotly_chart(fig_rel, use_container_width=True)
        
        # Calculate median lifetime (50% survival)
        median_life = -np.log(0.5) / lam
        st.markdown(f"""
        <div style="font-family: 'Inter', sans-serif; font-size: 0.75rem; color: rgba(255,255,255,0.5); line-height: 1.6;">
        <b>Median lifetime:</b> {median_life:,.0f} hours<br>
        <b>10% failure by:</b> {-np.log(0.9) / lam:,.0f} hours<br>
        <b>50% failure by:</b> {median_life:,.0f} hours
        </div>
        """, unsafe_allow_html=True)
    
    with st.expander("Understanding pack failures"):
        st.markdown("""
        **Exponential Distribution (Constant Hazard Rate):**
        - Pack failures are modeled as **memoryless** events — the probability of failure in the next hour is constant, regardless of pack age
        - This is appropriate for random failures: BMS faults, cell defects, connector damage, handling accidents
        - **MTBF** (Mean Time Between Failures): average operating hours between failures across the fleet
        - **MTTR** (Mean Time To Repair): average time to diagnose, swap, and repair a failed pack
        - **Availability** = MTBF / (MTBF + MTTR): percentage of time packs are operational
        
        **Interpretation:**
        - Higher MTBF = more reliable packs, fewer disruptions
        - Lower MTTR = faster turnaround, less downtime
        - This model assumes "sudden death" failures, not gradual degradation (which is captured separately by the SOH model)
        """)
    
    st.markdown("---")

# ---------------------------------------------------------------------------
# Charger Failure Model Preview (if enabled)
# ---------------------------------------------------------------------------
for idx, (show_charger_preview, charger_params) in enumerate(zip(charger_preview_flags, charger_preview_params)):
    if show_charger_preview and sim_engine == "stochastic":
        st.markdown("---")
        st.subheader(f"Charger Failure Model Preview: {charger_params['name']}")
        
        dist_type = charger_params['distribution']
        mtbf_hrs = charger_params['mtbf']
        mttr_hrs = charger_params['mttr']
        
        if dist_type == "exponential":
            st.caption("Exponential distribution (constant hazard rate)")
        else:
            beta = charger_params['weibull_shape']
            if beta < 1:
                st.caption(f"Weibull distribution (β = {beta:.2f}) — Infant mortality pattern")
            elif beta > 1:
                st.caption(f"Weibull distribution (β = {beta:.2f}) — Wear-out pattern")
            else:
                st.caption(f"Weibull distribution (β = {beta:.2f}) — Equivalent to exponential")
        
        # Time range (in hours)
        t_max = mtbf_hrs * 3
        t = np.linspace(0.01, t_max, 500)  # Start from 0.01 to avoid division by zero
        
        if dist_type == "exponential":
            # Exponential: λ = 1/MTBF
            lam = 1.0 / mtbf_hrs
            pdf = lam * np.exp(-lam * t)
            cdf = 1 - np.exp(-lam * t)
            reliability = np.exp(-lam * t)
            hazard_rate = np.full_like(t, lam)
            median_life = -np.log(0.5) / lam
        else:
            # Weibull: need to adjust scale parameter to match desired MTBF
            # MTBF = scale * Gamma(1 + 1/shape)
            # scale = MTBF / Gamma(1 + 1/shape)
            beta = charger_params['weibull_shape']
            scale = mtbf_hrs / gamma_func(1 + 1/beta)
            
            # Weibull PDF, CDF, reliability, hazard
            pdf = (beta / scale) * (t / scale) ** (beta - 1) * np.exp(-(t / scale) ** beta)
            cdf = 1 - np.exp(-(t / scale) ** beta)
            reliability = np.exp(-(t / scale) ** beta)
            hazard_rate = (beta / scale) * (t / scale) ** (beta - 1)
            median_life = scale * (np.log(2)) ** (1/beta)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Failure Probability**")
            fig_pdf = go.Figure()
            fig_pdf.add_trace(go.Scatter(
                x=t / 1000,
                y=pdf * 1000,
                mode='lines',
                name='PDF',
                line=dict(color='#fdcb6e', width=2),
                fill='tozeroy',
                fillcolor='rgba(253,203,110,0.2)',
            ))
            fig_pdf.add_vline(x=mtbf_hrs / 1000, line_dash="dash", line_color="#00b894",
                             annotation_text=f"MTBF: {mtbf_hrs/1000:.1f}k hrs",
                             annotation_position="top right")
            fig_pdf.update_layout(
                xaxis_title="Time (k hours)",
                yaxis_title="Probability Density (×10³)",
                height=280,
                margin=dict(l=20, r=20, t=30, b=20),
                showlegend=False,
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                font=dict(family="Inter", size=11, color="rgba(255,255,255,0.7)"),
            )
            st.plotly_chart(fig_pdf, use_container_width=True)
            
            st.markdown(f"""
            <div style="font-family: 'Inter', sans-serif; font-size: 0.75rem; color: rgba(255,255,255,0.5); line-height: 1.6;">
            <b>Distribution:</b> {dist_type.title()}<br>
            <b>MTBF:</b> {mtbf_hrs:,.0f} hours<br>
            <b>MTTR:</b> {mttr_hrs:.1f} hours<br>
            <b>Availability:</b> {100 * mtbf_hrs / (mtbf_hrs + mttr_hrs):.2f}%
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown("**Hazard Rate Over Time**")
            fig_hazard = go.Figure()
            fig_hazard.add_trace(go.Scatter(
                x=t / 1000,
                y=hazard_rate * 1000,
                mode='lines',
                name='Hazard Rate',
                line=dict(color='#fd79a8', width=2),
                fill='tozeroy',
                fillcolor='rgba(253,121,168,0.2)',
            ))
            fig_hazard.update_layout(
                xaxis_title="Time (k hours)",
                yaxis_title="Failure Rate (×10⁻³ per hour)",
                height=280,
                margin=dict(l=20, r=20, t=30, b=20),
                showlegend=False,
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                font=dict(family="Inter", size=11, color="rgba(255,255,255,0.7)"),
            )
            st.plotly_chart(fig_hazard, use_container_width=True)
            
            st.markdown(f"""
            <div style="font-family: 'Inter', sans-serif; font-size: 0.75rem; color: rgba(255,255,255,0.5); line-height: 1.6;">
            <b>Median lifetime:</b> {median_life:,.0f} hours<br>
            <b>10% failure by:</b> {t[np.argmin(np.abs(cdf - 0.1))]:,.0f} hours<br>
            <b>50% failure by:</b> {median_life:,.0f} hours
            </div>
            """, unsafe_allow_html=True)
        
        if dist_type == "weibull":
            with st.expander("Understanding Weibull shape parameter (β)"):
                st.markdown(f"""
                **Weibull Shape (β = {charger_params['weibull_shape']:.2f}):**
                
                - **β < 1** (Infant Mortality): Failure rate **decreases** over time
                  - Early defects and manufacturing issues get weeded out
                  - Common in electronics, new equipment
                  - Hazard rate is highest at t=0 and decays over time
                
                - **β = 1** (Constant Hazard): Equivalent to exponential distribution
                  - Random, memoryless failures
                  - Hazard rate is flat over time
                
                - **β > 1** (Wear-out): Failure rate **increases** over time
                  - Mechanical wear, fatigue, aging effects dominate
                  - Typical for mature equipment approaching end-of-life
                  - Hazard rate accelerates as equipment ages
                
                **Your Configuration (β = {charger_params['weibull_shape']:.2f}):**
                {"- Infant mortality pattern: expect more failures early, then stabilizing" if charger_params['weibull_shape'] < 1 else ""}
                {"- Constant failure rate: random failures, no age dependence" if charger_params['weibull_shape'] == 1 else ""}
                {"- Wear-out pattern: failures increase with age, consider proactive replacement" if charger_params['weibull_shape'] > 1 else ""}
                """)
        else:
            with st.expander("Understanding exponential failures"):
                st.markdown("""
                **Exponential Distribution (Constant Hazard Rate):**
                - Charger failures are **memoryless** — failure probability is constant regardless of age
                - Appropriate for random failures: power supply faults, connector wear, software glitches
                - **MTBF** (Mean Time Between Failures): average operating hours per charger between failures
                - **MTTR** (Mean Time To Repair): average time to diagnose, repair, or replace a charger
                - **Availability** = MTBF / (MTBF + MTTR): fraction of time chargers are operational
                
                **When to use exponential vs Weibull:**
                - Use **exponential** for proven, mature technology with random failures
                - Use **Weibull with β < 1** for new technology with early-life issues
                - Use **Weibull with β > 1** for equipment with known wear-out patterns
                """)
        
        st.markdown("---")

if not (run_clicked or "results" in st.session_state):
    st.markdown("""
    <div style="
        background: linear-gradient(135deg, rgba(108,92,231,0.10), rgba(9,132,227,0.06));
        border: 1px solid rgba(108,92,231,0.18);
        border-radius: 10px;
        padding: 48px 32px;
        text-align: center;
        margin: 2rem 0;
    ">
        <div style="font-size: 2rem; margin-bottom: 6px;">⚡</div>
        <div style="font-family: 'Inter', sans-serif; font-size: 1.15rem; font-weight: 700; color: #fff; margin-bottom: 4px; letter-spacing: -0.3px;">Ready to Simulate</div>
        <div style="font-family: 'Inter', sans-serif; color: rgba(255,255,255,0.42); font-size: 0.82rem; font-weight: 400;">Configure your scenario in the sidebar, then click <b>Run Simulation</b></div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

# ---------------------------------------------------------------------------
# RUN ENGINE
# ---------------------------------------------------------------------------
with st.spinner("Running simulation…" if sim_engine == "static" else f"Running {sim_mc} Monte-Carlo simulations…"):
    results: list[SimulationResult] = [run_engine(scenario, cv) for cv in charger_variants]
st.session_state["results"] = results

# Dynamic subtitle
_is_stochastic = results[0].engine_type == "stochastic"
_has_mc = results[0].monte_carlo is not None
if _is_stochastic:
    _phase_label = f"Phase 2 — Stochastic Engine · {sim_mc} MC runs · seed={sim_seed}" if _has_mc else "Phase 2 — Single Stochastic Run"
else:
    _phase_label = "Phase 1 — Static Unit Economics"
st.caption(f"{_phase_label} · Finance · Intelligence · Show the Math")

# Shorthand refs used throughout
v = vehicle
p = pack
multi_charger = len(results) > 1


# ═══════════════════════════════════════════════════════════════════════════
# ==============================  MAIN TABS  ==============================
# ═══════════════════════════════════════════════════════════════════════════
operations_tab, finance_tab, intelligence_tab = st.tabs(["Operations", "Finance", "Intelligence"])


# ═══════════════════════════════════════════════════════════════════════════
# ==================  OPERATIONS TAB  =====================================
# ═══════════════════════════════════════════════════════════════════════════
with operations_tab:

    # ── SECTION 1 — Operational Overview ─────────────────────────────────
    st.divider()
    st.header("Operational Overview")

    d0 = results[0].derived

    # --- Fleet composition — styled cards ---
    st.subheader("Fleet Composition")
    fi_cols = st.columns(5)
    fi_cards = [
        ("🚗", "Fleet Size", f"{d0.initial_fleet_size:,}", "#6c5ce7"),
        ("⚡", "Charging Docks", f"{d0.total_docks:,}", "#00b894"),
        ("🔋", "Active Packs", f"{d0.packs_on_vehicles:,}", "#0984e3"),
        ("🔌", "Float Packs", f"{d0.packs_in_docks:,}", "#fdcb6e"),
        ("📦", "Total Inventory", f"{d0.total_packs:,}", "#e17055"),
    ]
    for col, (icon, label, value, accent) in zip(fi_cols, fi_cards):
        col.markdown(_card(icon, label, value, accent), unsafe_allow_html=True)

    with st.expander("Show inventory formulas"):
        st.markdown(f"**Active packs** — `fleet × packs_per_vehicle` = {d0.initial_fleet_size:,} × {v.packs_per_vehicle} = **{d0.packs_on_vehicles:,}**")
        st.markdown(f"**Float packs** — `stations × docks_per_station` = {station.num_stations} × {station.docks_per_station} = **{d0.packs_in_docks:,}**")
        st.markdown(f"**Total inventory** — {d0.packs_on_vehicles:,} + {d0.packs_in_docks:,} = **{d0.total_packs:,}**")

    # --- Key operating metrics ---
    st.subheader("Key Operating Metrics")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Energy per Swap", f"{d0.energy_per_swap_cycle_per_pack_kwh:.3f} kWh",
              help="Energy consumed from one pack per swap cycle (per pack)")
    m2.metric("Daily Swaps per Vehicle", f"{d0.swap_visits_per_vehicle_per_day:.2f}",
              help="Station visits per vehicle per day — all packs swapped per visit")
    m3.metric("Pack Cycle Life", f"{d0.pack_lifetime_cycles:,} cycles")
    m4.metric("Energy per Visit", f"{d0.energy_per_swap_cycle_per_vehicle_kwh:.2f} kWh",
              help="Total energy refilled per swap visit (all packs × energy per pack)")

    # --- Per-charger derived ---
    if multi_charger:
        cols = st.columns(len(results))
        for col, res in zip(cols, results):
            dd = res.derived
            col.markdown(f"**{res.charger_variant_id}**")
            col.metric("Charge Duration", f"{dd.charge_time_minutes:.1f} min")
            col.metric("Effective C-Rate", f"{dd.effective_c_rate:.2f} C")
            col.metric("Cycles per Dock / Day", f"{dd.cycles_per_day_per_dock:.1f}")
    else:
        dd = d0
        m1, m2, m3 = st.columns(3)
        m1.metric("Charge Duration", f"{dd.charge_time_minutes:.1f} min")
        m2.metric("Effective C-Rate", f"{dd.effective_c_rate:.2f} C")
        m3.metric("Cycles per Dock / Day", f"{dd.cycles_per_day_per_dock:.1f}")

    # --- Formula detail ---
    with st.expander("Show operating formulas"):
        rated_kw_0 = charger_variants[0].rated_power_w / 1000
        formulas = {
            "Energy per swap cycle (per pack)": (
                "`capacity × (1 − range_anxiety_buffer)`  ← driver-behaviour assumption, not hard limit",
                f"{v.pack_capacity_kwh} × (1 − {v.range_anxiety_buffer_pct:.2f}) = **{d0.energy_per_swap_cycle_per_pack_kwh:.4f} kWh**",
            ),
            "Energy per swap visit (per vehicle)": (
                "`packs_per_vehicle × energy_per_pack`",
                f"{v.packs_per_vehicle} × {d0.energy_per_swap_cycle_per_pack_kwh:.4f} = **{d0.energy_per_swap_cycle_per_vehicle_kwh:.4f} kWh**",
            ),
            "Daily energy need": (
                "`daily_km × Wh_per_km`",
                f"{v.avg_daily_km} × {v.energy_consumption_wh_per_km} = **{d0.daily_energy_need_wh:,.0f} Wh**",
            ),
            "Swap visits / day / vehicle": (
                "`energy_need_Wh / energy_per_visit_Wh`  ← visits, not individual pack swaps",
                f"{d0.daily_energy_need_wh:,.0f} / {d0.energy_per_swap_cycle_per_vehicle_kwh * 1000:,.0f} = **{d0.swap_visits_per_vehicle_per_day:.4f}**",
            ),
            "Charge time": (
                "`capacity / (power_kW × efficiency) × 60`",
                f"{v.pack_capacity_kwh} / ({rated_kw_0} × {charger_variants[0].charging_efficiency_pct}) × 60 = **{d0.charge_time_minutes:.2f} min**",
            ),
            "Effective C-rate": (
                "`power_kW / capacity`",
                f"{rated_kw_0} / {v.pack_capacity_kwh} = **{d0.effective_c_rate:.4f} C**",
            ),
            "Cycles / day / dock": (
                "`(op_hours × 60) / charge_time`",
                f"({station.operating_hours_per_day} × 60) / {d0.charge_time_minutes:.2f} = **{d0.cycles_per_day_per_dock:.2f}**",
            ),
            "Pack lifetime cycles": (
                "`(1 − retirement_SOH) / (β/100 × aggressiveness)`",
                f"(1.0 − {p.retirement_soh_pct}) / ({p.cycle_degradation_rate_pct} / 100 × {chaos_cfg.aggressiveness_index}) = **{d0.pack_lifetime_cycles:,}**",
            ),
        }
        for name, (formula, calc) in formulas.items():
            st.markdown(f"**{name}** — {formula}  \n{calc}")

    # ── SECTION 2 — Unit Economics ──────────────────────────────────────
    st.divider()
    st.header("Unit Economics")

    def _render_cpc_block(res: SimulationResult, show_label: bool = False):
        """Render CPC chart, table, swap economics, and TCO breakdowns."""
        cv = next(c for c in charger_variants if c.name == res.charger_variant_id)
        cpc = res.cpc_waterfall
        tco = res.charger_tco
        dd = res.derived
        ptco = res.pack_tco

        if show_label:
            st.markdown(f"#### {res.charger_variant_id}")

        cost_per_visit = cpc.total * v.packs_per_vehicle
        rev_per_visit = revenue_cfg.price_per_swap
        margin = rev_per_visit - cost_per_visit
        margin_color = "#00b894" if margin >= 0 else "#d63031"

        h_cols = st.columns(4)
        h_cards = [
            ("💰", "Cost per Cycle", f"₹{cpc.total:.2f}", "#6c5ce7"),
            ("📈", "Revenue per Visit", f"₹{rev_per_visit:.2f}", "#00b894"),
            ("📉", "Cost per Visit", f"₹{cost_per_visit:.2f}", "#0984e3"),
            ("🎯", "Margin per Visit", f"₹{margin:.2f}", margin_color),
        ]
        for col, (icon, label, value, accent) in zip(h_cols, h_cards):
            col.markdown(_card(icon, label, value, accent), unsafe_allow_html=True)
        st.write("")

        components = [
            ("Battery", cpc.battery), ("Charger", cpc.charger),
            ("Electricity", cpc.electricity), ("Real estate", cpc.real_estate),
            ("Maintenance", cpc.maintenance), ("Insurance", cpc.insurance),
            ("Sabotage", cpc.sabotage), ("Logistics", cpc.logistics),
            ("Overhead", cpc.overhead),
        ]

        chart_data = {name: [val] for name, val in components}
        st.bar_chart(chart_data, horizontal=True, height=280, y_label="₹ / cycle", use_container_width=True)

        cpc_table_rows = []
        for name, val in components:
            pct = (val / cpc.total * 100) if cpc.total > 0 else 0
            cpc_table_rows.append({"Component": name, "₹ / cycle": round(val, 4), "% of total": f"{pct:.1f}%"})
        cpc_table_rows.append({"Component": "TOTAL", "₹ / cycle": round(cpc.total, 4), "% of total": "100%"})
        st.dataframe(cpc_table_rows, use_container_width=True, hide_index=True)

        with st.expander("Show CPC formulas"):
            batt_degrad = (p.unit_cost - p.second_life_salvage_value) / dd.pack_lifetime_cycles if dd.pack_lifetime_cycles > 0 else 0.0
            cpc_formulas = [
                ("Battery", "`degradation + pack_failure_cost`",
                 f"degradation = ({p.unit_cost:,.0f} − {p.second_life_salvage_value:,.0f}) / {dd.pack_lifetime_cycles:,} = ₹{batt_degrad:.4f}  \n"
                 f"failure = pack_failure_TCO / fleet_cycles = {ptco.total_failure_tco:,.0f} / {ptco.fleet_operating_hours:,.0f} → **₹{ptco.failure_cost_per_cycle:.4f}**  \n"
                 f"total = ₹{batt_degrad:.4f} + ₹{ptco.failure_cost_per_cycle:.4f} = **₹{cpc.battery:.4f}**"),
                ("Charger", "`charger_TCO / cycles_served`",
                 f"{tco.total_tco:,.0f} / {tco.cycles_served_over_horizon:,.0f} = **₹{cpc.charger:.4f}**"),
                ("Electricity", "`(capacity / efficiency) × tariff`",
                 f"({p.nominal_capacity_kwh} / {cv.charging_efficiency_pct}) × {opex_cfg.electricity_tariff_per_kwh} = **₹{cpc.electricity:.4f}**"),
                ("Real estate", "`rent / cycles_per_month`",
                 f"{opex_cfg.rent_per_month_per_station:,.0f} / {dd.cycles_per_month_per_station:,.0f} = **₹{cpc.real_estate:.4f}**"),
                ("Maintenance", "`(prev + corr) / cycles_per_month`",
                 f"({opex_cfg.preventive_maintenance_per_month_per_station:,.0f} + {opex_cfg.corrective_maintenance_per_month_per_station:,.0f}) / {dd.cycles_per_month_per_station:,.0f} = **₹{cpc.maintenance:.4f}**"),
                ("Insurance", "`premium / cycles_per_month`",
                 f"{opex_cfg.insurance_per_month_per_station:,.0f} / {dd.cycles_per_month_per_station:,.0f} = **₹{cpc.insurance:.4f}**"),
                ("Sabotage", "`(docks × sab% × pack_cost) / cycles_per_month`",
                 f"({station.docks_per_station} × {chaos_cfg.sabotage_pct_per_month} × {p.unit_cost:,.0f}) / {dd.cycles_per_month_per_station:,.0f} = **₹{cpc.sabotage:.4f}**"),
                ("Logistics", "`logistics / cycles_per_month`",
                 f"{opex_cfg.logistics_per_month_per_station:,.0f} / {dd.cycles_per_month_per_station:,.0f} = **₹{cpc.logistics:.4f}**"),
                ("Overhead", "`overhead / network_cycles_per_month`",
                 f"{opex_cfg.overhead_per_month:,.0f} / {dd.total_network_cycles_per_month:,.0f} = **₹{cpc.overhead:.4f}**"),
            ]
            for name, formula, calc in cpc_formulas:
                st.markdown(f"**{name}** — {formula}  \n{calc}")

        with st.expander("Charger TCO breakdown (fleet-level)"):
            per_dock_hrs = tco.scheduled_hours_per_year_per_dock * sim_cfg.horizon_months / 12
            st.caption(f"MTBF is a population statistic — all figures below are for the entire fleet of **{tco.total_docks}** docks.")
            tco_rows = [
                {"Item": "Total docks", "Value": f"{tco.total_docks}"},
                {"Item": "Purchase cost (fleet)", "Value": f"₹{tco.purchase_cost:,.0f}"},
                {"Item": "Scheduled hrs / yr / dock", "Value": f"{tco.scheduled_hours_per_year_per_dock:,.0f} hrs"},
                {"Item": f"Fleet operating hours ({sim_cfg.horizon_months/12:.0f} yr)", "Value": f"{tco.fleet_operating_hours:,.0f} hrs"},
                {"Item": "Availability  MTBF/(MTBF+MTTR)", "Value": f"{tco.availability:.4f}  ({tco.availability*100:.2f}%)"},
                {"Item": f"Expected failures — fleet ({sim_cfg.horizon_months/12:.0f} yr)", "Value": f"{tco.expected_failures_over_horizon:.2f}"},
                {"Item": "Total repair cost (fleet)", "Value": f"₹{tco.total_repair_cost:,.0f}"},
                {"Item": "Full replacements (fleet)", "Value": f"{tco.num_replacements}"},
                {"Item": "Replacement cost (fleet)", "Value": f"₹{tco.total_replacement_cost:,.0f}"},
                {"Item": "Downtime (fleet dock-hours)", "Value": f"{tco.total_downtime_hours:.1f} hrs"},
                {"Item": "Lost revenue (downtime)", "Value": f"₹{tco.lost_revenue_from_downtime:,.0f}"},
                {"Item": "Spare inventory (fleet)", "Value": f"₹{tco.spare_inventory_cost:,.0f}"},
                {"Item": "TOTAL TCO (fleet)", "Value": f"₹{tco.total_tco:,.0f}"},
                {"Item": "Cycles served (fleet)", "Value": f"{tco.cycles_served_over_horizon:,.0f}"},
                {"Item": "Cost per cycle", "Value": f"₹{tco.cost_per_cycle:.4f}"},
            ]
            st.dataframe(tco_rows, use_container_width=True, hide_index=True)

            with st.expander("Show TCO formulas"):
                st.markdown(f"**Per-dock hours** — `hrs/day × 365 × years` = {station.operating_hours_per_day} × 365 × {sim_cfg.horizon_months/12:.0f} = **{per_dock_hrs:,.0f} hrs**")
                st.markdown(f"**Fleet operating hours** — `per_dock × total_docks` = {per_dock_hrs:,.0f} × {tco.total_docks} = **{tco.fleet_operating_hours:,.0f} hrs**")
                st.markdown(f"**Fleet failures** — `fleet_hours / MTBF` = {tco.fleet_operating_hours:,.0f} / {cv.mtbf_hours:,.0f} = **{tco.expected_failures_over_horizon:.2f}**")
                st.markdown(f"**Downtime** — `failures × MTTR` = {tco.expected_failures_over_horizon:.2f} × {cv.mttr_hours} = **{tco.total_downtime_hours:.1f} dock-hrs**")
                st.markdown(f"**Availability** — `MTBF / (MTBF + MTTR)` = {cv.mtbf_hours:,.0f} / ({cv.mtbf_hours:,.0f} + {cv.mttr_hours}) = **{tco.availability*100:.2f}%** ← steady-state statistic")
                st.markdown(f"**Fleet repairs** — `failures × repair_cost` = {tco.expected_failures_over_horizon:.2f} × {cv.repair_cost_per_event:,.0f} = **₹{tco.total_repair_cost:,.0f}**")
                st.markdown(f"**Fleet replacements** — `floor(failures / threshold)` = floor({tco.expected_failures_over_horizon:.2f} / {cv.replacement_threshold}) = **{tco.num_replacements}**")

        with st.expander("Pack failure TCO breakdown (fleet-level)"):
            st.caption(f"MTBF is a population statistic — all figures below are for the entire pack fleet of **{ptco.total_packs}** packs.")
            ptco_rows = [
                {"Item": "Total packs in fleet", "Value": f"{ptco.total_packs}"},
                {"Item": f"Fleet operating hours ({sim_cfg.horizon_months/12:.0f} yr)", "Value": f"{ptco.fleet_operating_hours:,.0f} hrs"},
                {"Item": "Availability  MTBF/(MTBF+MTTR)", "Value": f"{ptco.availability:.4f}  ({ptco.availability*100:.2f}%)"},
                {"Item": f"Expected failures — fleet ({sim_cfg.horizon_months/12:.0f} yr)", "Value": f"{ptco.expected_failures:.2f}"},
                {"Item": "Total repair cost (fleet)", "Value": f"₹{ptco.total_repair_cost:,.0f}"},
                {"Item": "Full replacements (fleet)", "Value": f"{ptco.num_replacements}"},
                {"Item": "Replacement cost (fleet)", "Value": f"₹{ptco.total_replacement_cost:,.0f}"},
                {"Item": "Downtime (fleet pack-hours)", "Value": f"{ptco.total_downtime_hours:.1f} hrs"},
                {"Item": "Lost revenue (downtime)", "Value": f"₹{ptco.lost_revenue_from_downtime:,.0f}"},
                {"Item": "Spare inventory (fleet)", "Value": f"₹{ptco.spare_inventory_cost:,.0f}"},
                {"Item": "TOTAL failure TCO (fleet)", "Value": f"₹{ptco.total_failure_tco:,.0f}"},
                {"Item": "Failure cost per cycle", "Value": f"₹{ptco.failure_cost_per_cycle:.4f}"},
            ]
            st.dataframe(ptco_rows, use_container_width=True, hide_index=True)

            with st.expander("Show pack TCO formulas"):
                st.markdown(f"**Fleet operating hours** — `hrs/day × 365 × years × packs` = {station.operating_hours_per_day} × 365 × {sim_cfg.horizon_months/12:.0f} × {ptco.total_packs} = **{ptco.fleet_operating_hours:,.0f} hrs**")
                st.markdown(f"**Fleet failures** — `fleet_hours / MTBF` = {ptco.fleet_operating_hours:,.0f} / {p.mtbf_hours:,.0f} = **{ptco.expected_failures:.2f}**")
                st.markdown(f"**Downtime** — `failures × MTTR` = {ptco.expected_failures:.2f} × {p.mttr_hours} = **{ptco.total_downtime_hours:.1f} pack-hrs**")
                st.markdown(f"**Availability** — `MTBF / (MTBF + MTTR)` = {p.mtbf_hours:,.0f} / ({p.mtbf_hours:,.0f} + {p.mttr_hours}) = **{ptco.availability*100:.2f}%**")
                st.markdown(f"**Fleet repairs** — `failures × repair_cost` = {ptco.expected_failures:.2f} × {p.repair_cost_per_event:,.0f} = **₹{ptco.total_repair_cost:,.0f}**")
                st.markdown(f"**Fleet replacements** — `floor(failures / threshold)` = floor({ptco.expected_failures:.2f} / {p.replacement_threshold}) = **{ptco.num_replacements}**")

    if multi_charger:
        cpc_tabs = st.tabs([r.charger_variant_id for r in results])
        for cpc_tab, res in zip(cpc_tabs, results):
            with cpc_tab:
                _render_cpc_block(res)
    else:
        _render_cpc_block(results[0])

    # ── SECTION 3 — Cash Flow Timeline ──────────────────────────────────
    st.divider()
    st.header("Cash Flow Timeline")

    if multi_charger:
        cf_chart_data = {}
        for res in results:
            cf_chart_data[res.charger_variant_id] = [s.cumulative_cash_flow for s in res.months]
        st.line_chart(cf_chart_data, y_label="Cumulative Cash Flow (₹)", x_label="Month", height=320, use_container_width=True)
    else:
        cf_chart_data = {"Cumulative CF": [s.cumulative_cash_flow for s in results[0].months]}
        st.line_chart(cf_chart_data, y_label="Cumulative Cash Flow (₹)", x_label="Month", height=320, use_container_width=True)

    if multi_charger:
        be_cols = st.columns(len(results))
        for col, res in zip(be_cols, results):
            if res.summary.break_even_month:
                be_snap = res.months[res.summary.break_even_month - 1]
                col.success(f"**{res.charger_variant_id}**  \nBreak-even: **month {res.summary.break_even_month}** ({be_snap.fleet_size:,} vehicles)")
            else:
                col.warning(f"**{res.charger_variant_id}**  \nNo break-even in {sim_cfg.horizon_months} months")
    else:
        res0 = results[0]
        if res0.summary.break_even_month:
            be_snap = res0.months[res0.summary.break_even_month - 1]
            st.success(f"Break-even: **month {res0.summary.break_even_month}** ({be_snap.fleet_size:,} vehicles)")
        else:
            st.warning(f"No break-even within {sim_cfg.horizon_months} months")

    def _render_cf_block(res: SimulationResult):
        cf_rows = []
        is_stoch = res.engine_type == "stochastic"
        for s in res.months:
            row = {
                "Month": s.month, "Fleet": s.fleet_size,
                "Visits": s.swap_visits, "Cycles": s.total_cycles,
                "Revenue (₹)": round(s.revenue),
                "OpEx (₹)": round(s.opex_total),
                "CapEx (₹)": round(s.capex_this_month),
                "Net CF (₹)": round(s.net_cash_flow),
                "Cum. CF (₹)": round(s.cumulative_cash_flow),
            }
            if is_stoch:
                row["SOH"] = f"{s.avg_soh:.2%}" if s.avg_soh is not None else "—"
                row["Retired"] = s.packs_retired_this_month or 0
                row["Repl. CapEx (₹)"] = round(s.replacement_capex_this_month or 0)
                row["Chrg Fails"] = s.charger_failures_this_month or 0
            cf_rows.append(row)
        st.dataframe(cf_rows, use_container_width=True, hide_index=True, height=min(400, 35 * len(cf_rows) + 38))

        sm = res.summary
        ncf_color = "#00b894" if sm.total_net_cash_flow >= 0 else "#d63031"
        sm_cols = st.columns(4)
        sm_cards = [
            ("📈", "Cumulative Revenue", _fmt_inr(sm.total_revenue), "#00b894"),
            ("💸", "Cumulative OpEx", _fmt_inr(sm.total_opex), "#e17055"),
            ("🏗️", "Cumulative CapEx", _fmt_inr(sm.total_capex), "#0984e3"),
            ("💎", "Net Cash Flow", _fmt_inr(sm.total_net_cash_flow), ncf_color),
        ]
        for col, (icon, label, value, accent) in zip(sm_cols, sm_cards):
            col.markdown(_card(icon, label, value, accent), unsafe_allow_html=True)

    if multi_charger:
        cf_tabs = st.tabs([r.charger_variant_id for r in results])
        for cf_tab, res in zip(cf_tabs, results):
            with cf_tab:
                _render_cf_block(res)
    else:
        _render_cf_block(results[0])

    # ── SECTION 4 — Charger Comparison ──────────────────────────────────
    if multi_charger:
        st.divider()
        st.header("Charger Variant Comparison")
        best = min(results, key=lambda r: r.cpc_waterfall.total)
        comp_rows = []
        for res in results:
            cv = next(c for c in charger_variants if c.name == res.charger_variant_id)
            cpc = res.cpc_waterfall
            dd = res.derived
            cost_per_visit = cpc.total * v.packs_per_vehicle
            rev_per_visit = revenue_cfg.price_per_swap
            comp_rows.append({
                "Charger": cv.name,
                "Cost / slot (₹)": f"{cv.purchase_cost_per_slot:,.0f}",
                "MTBF (hrs)": f"{cv.mtbf_hours:,.0f}",
                "Charge time": f"{dd.charge_time_minutes:.1f} min",
                "C-rate": f"{dd.effective_c_rate:.2f}",
                "Fleet TCO (₹)": _fmt_inr(res.charger_tco.total_tco),
                "CPC (₹/cycle)": f"{cpc.total:.2f}",
                "Charger CPC (₹)": f"{cpc.charger:.4f}",
                "Cost / visit (₹)": f"{cost_per_visit:.2f}",
                "Margin / visit (₹)": f"{rev_per_visit - cost_per_visit:.2f}",
                "Break-even": f"Mo. {res.summary.break_even_month}" if res.summary.break_even_month else "Never",
                f"Net CF ({sim_cfg.horizon_months//12}yr)": _fmt_inr(res.summary.total_net_cash_flow),
            })
        st.dataframe(comp_rows, use_container_width=True, hide_index=True)
        st.success(f"✅ **{best.charger_variant_id}** has the lowest cost per cycle at **₹{best.cpc_waterfall.total:.2f}**.")

    # ── Phase 2 dynamic sections ────────────────────────────────────────
    _next_section = 5 if multi_charger else 4

    if _has_mc:
        st.divider()
        _mc_section = _next_section
        _next_section += 1
        st.header("Monte Carlo Analysis")

        def _render_mc_block(res: SimulationResult):
            mc = res.monte_carlo
            if mc is None:
                return
            st.markdown(f"**{res.charger_variant_id}** — {mc.num_runs} simulations")
            st.subheader("Net Cash Flow Distribution")
            mc_cols = st.columns(3)
            mc_ncf_cards = [
                ("📉", "P10 — Pessimistic", _fmt_inr(mc.ncf_p10), "#d63031"),
                ("📊", "P50 — Median", _fmt_inr(mc.ncf_p50), "#6c5ce7"),
                ("📈", "P90 — Optimistic", _fmt_inr(mc.ncf_p90), "#00b894"),
            ]
            for col, (icon, label, value, accent) in zip(mc_cols, mc_ncf_cards):
                col.markdown(_card(icon, label, value, accent), unsafe_allow_html=True)
            st.write("")
            mc_cols2 = st.columns(4)
            be_p10_str = f"Month {mc.break_even_p10}" if mc.break_even_p10 else "Never"
            be_p50_str = f"Month {mc.break_even_p50}" if mc.break_even_p50 else "Never"
            be_p90_str = f"Month {mc.break_even_p90}" if mc.break_even_p90 else "Never"
            mc_detail_cards = [
                ("🕐", "Break-even — Median", be_p50_str, "#6c5ce7"),
                ("⏳", "Break-even — Range", f"{be_p10_str} – {be_p90_str}", "#0984e3"),
                ("💰", "CPC — Median", f"₹{mc.cpc_p50:.2f}", "#6c5ce7"),
                ("📊", "CPC — Range", f"₹{mc.cpc_p10:.2f} – ₹{mc.cpc_p90:.2f}", "#0984e3"),
            ]
            for col, (icon, label, value, accent) in zip(mc_cols2, mc_detail_cards):
                col.markdown(_card(icon, label, value, accent), unsafe_allow_html=True)
            st.write("")
            mc_cols3 = st.columns(4)
            mc_fleet_cards = [
                ("🔋", "Avg Packs Retired", f"{mc.avg_packs_retired:.0f}", "#e17055"),
                ("🔋", "Max Packs Retired", f"{mc.max_packs_retired}", "#d63031"),
                ("⚡", "Avg Charger Failures", f"{mc.avg_charger_failures:.0f}", "#fdcb6e"),
                ("🚫", "Worst-Case Unserved", f"{mc.max_failure_to_serve}", "#d63031"),
            ]
            for col, (icon, label, value, accent) in zip(mc_cols3, mc_fleet_cards):
                col.markdown(_card(icon, label, value, accent), unsafe_allow_html=True)

        if multi_charger:
            mc_tabs = st.tabs([r.charger_variant_id for r in results])
            for mc_tab, res in zip(mc_tabs, results):
                with mc_tab:
                    _render_mc_block(res)
        else:
            _render_mc_block(results[0])

    if _is_stochastic:
        st.divider()
        _health_section = _next_section
        _next_section += 1
        st.header("Battery Health Tracker")

        def _render_health_block(res: SimulationResult):
            months_data = res.months
            if not months_data or months_data[0].avg_soh is None:
                st.info("No battery health data for this run.")
                return
            sm = res.summary
            h_cols = st.columns(4)
            h_cards = [
                ("🔋", "Final Fleet SOH", f"{sm.mean_soh_at_end:.1%}" if sm.mean_soh_at_end else "—", "#00b894"),
                ("♻️", "Packs Retired", f"{sm.total_packs_retired or 0:,}", "#e17055"),
                ("💰", "Replacement Cost", _fmt_inr(sm.total_replacement_capex or 0), "#d63031"),
                ("🔄", "Salvage Recovery", _fmt_inr(sm.total_salvage_credit or 0), "#fdcb6e"),
            ]
            for col, (icon, label, value, accent) in zip(h_cols, h_cards):
                col.markdown(_card(icon, label, value, accent), unsafe_allow_html=True)
            st.write("")
            st.subheader("Average SOH Trend")
            soh_data = {"SOH": [m.avg_soh for m in months_data]}
            st.line_chart(soh_data, y_label="State of Health", x_label="Month", height=280, use_container_width=True)
            st.subheader("Replacement CapEx Timeline")
            capex_data = {"Replacement CapEx (₹)": [m.replacement_capex_this_month or 0 for m in months_data]}
            st.bar_chart(capex_data, y_label="₹", x_label="Month", height=280, use_container_width=True, color=["#e17055"])
            st.caption("Spikes represent cohort retirements — the real cash flow pattern investors must plan for.")
            retirement_months = [m for m in months_data if (m.packs_retired_this_month or 0) > 0]
            if retirement_months:
                with st.expander(f"Retirement events ({len(retirement_months)} months)"):
                    ret_rows = []
                    for m in retirement_months:
                        ret_rows.append({
                            "Month": m.month,
                            "Packs Retired": m.packs_retired_this_month,
                            "Replacement CapEx (₹)": f"₹{m.replacement_capex_this_month:,.0f}" if m.replacement_capex_this_month else "₹0",
                            "Salvage Credit (₹)": f"₹{m.salvage_credit_this_month:,.0f}" if m.salvage_credit_this_month else "₹0",
                            "Fleet SOH": f"{m.avg_soh:.1%}" if m.avg_soh else "—",
                        })
                    st.dataframe(ret_rows, use_container_width=True, hide_index=True)
            if res.cohort_history and len(res.cohort_history) > 0:
                final_cohorts = res.cohort_history[-1]
                with st.expander(f"Pack cohorts at month {len(months_data)} ({len(final_cohorts)} cohorts)"):
                    cohort_rows = []
                    for c in final_cohorts:
                        cohort_rows.append({
                            "Cohort": c.cohort_id, "Born": f"Month {c.born_month}",
                            "Packs": c.pack_count, "SOH": f"{c.current_soh:.1%}",
                            "Cycles": f"{c.cumulative_cycles:,}",
                            "Status": "🔴 Retired" if c.is_retired else "🟢 Active",
                            "Retired at": f"Month {c.retired_month}" if c.retired_month else "—",
                        })
                    st.dataframe(cohort_rows, use_container_width=True, hide_index=True)

        if multi_charger:
            h_tabs = st.tabs([r.charger_variant_id for r in results])
            for h_tab, res in zip(h_tabs, results):
                with h_tab:
                    _render_health_block(res)
        else:
            _render_health_block(results[0])

    if _is_stochastic:
        st.divider()
        _rel_section = _next_section
        _next_section += 1
        st.header("Charger Reliability")

        def _render_reliability_block(res: SimulationResult):
            months_data = res.months
            if not months_data or months_data[0].charger_failures_this_month is None:
                st.info("No charger failure data for this run.")
                return
            sm = res.summary
            cv = next(c for c in charger_variants if c.name == res.charger_variant_id)
            r_cols = st.columns(4)
            r_cards = [
                ("⚡", "Total Failures", f"{sm.total_charger_failures or 0:,}", "#e17055"),
                ("🛠️", "Mean Time Between Failures", f"{cv.mtbf_hours:,.0f} hrs", "#0984e3"),
                ("⏱️", "Mean Time to Repair", f"{cv.mttr_hours:.0f} hrs", "#fdcb6e"),
                ("📊", "Failure Distribution", cv.failure_distribution.title(), "#6c5ce7"),
            ]
            for col, (icon, label, value, accent) in zip(r_cols, r_cards):
                col.markdown(_card(icon, label, value, accent), unsafe_allow_html=True)
            st.write("")
            st.subheader("Monthly Failure Events")
            fail_data = {"Failures": [m.charger_failures_this_month or 0 for m in months_data]}
            st.bar_chart(fail_data, y_label="Failures", x_label="Month", height=250, use_container_width=True, color=["#fdcb6e"])
            if cv.failure_distribution == "weibull" and cv.weibull_shape > 1:
                st.caption(f"Weibull β = {cv.weibull_shape} → wear-out pattern: failures increase with charger age.")
            elif cv.failure_distribution == "weibull" and cv.weibull_shape < 1:
                st.caption(f"Weibull β = {cv.weibull_shape} → infant mortality: failures decrease as early defects are weeded out.")

        if multi_charger:
            rel_tabs = st.tabs([r.charger_variant_id for r in results])
            for rel_tab, res in zip(rel_tabs, results):
                with rel_tab:
                    _render_reliability_block(res)
        else:
            _render_reliability_block(results[0])


# ═══════════════════════════════════════════════════════════════════════════
# ==================  FINANCE TAB  ========================================
# ═══════════════════════════════════════════════════════════════════════════
with finance_tab:

    st.divider()
    st.header("Financial Overview")
    st.caption("DCF · Debt Schedule · DSCR · P&L · Cash Flow Statement")

    # ── Compute finance for first charger (or primary) ──────────────────
    def _compute_finance(res: SimulationResult, cv: ChargerVariant):
        """Run all Phase 3 finance modules for one charger variant."""
        d = res.derived
        per_station_capex = (
            station.cabinet_cost + station.site_prep_cost
            + station.grid_connection_cost + station.security_deposit
        )
        total_initial_capex = (
            per_station_capex * station.num_stations + station.software_cost
            + cv.purchase_cost_per_slot * d.total_docks
            + p.unit_cost * d.total_packs
        )
        total_salvage = d.total_packs * p.second_life_salvage_value

        dcf = build_dcf_table(
            res.months, res.summary, finance_cfg,
            sim_cfg.discount_rate_annual, total_salvage,
        )
        debt = build_debt_schedule(total_initial_capex, finance_cfg, sim_cfg.horizon_months)
        dscr = compute_dscr(res.months, debt, finance_cfg, total_salvage)
        stmts = build_financial_statements(
            res.months, debt, finance_cfg, opex_cfg, station, p, cv, total_initial_capex,
        )
        charger_npv = compute_charger_npv(cv, res.charger_tco, d, sim_cfg, station)

        return total_initial_capex, dcf, debt, dscr, stmts, charger_npv

    # ── Render finance for one variant ──────────────────────────────────
    def _render_finance_block(res: SimulationResult, cv: ChargerVariant):
        total_capex, dcf, debt, dscr, stmts, cnpv = _compute_finance(res, cv)

        # ── DCF headline metrics ────────────────────────────────────────
        st.subheader("Discounted Cash Flow (DCF)")
        dcf_cols = st.columns(4)
        npv_color = "#00b894" if dcf.npv >= 0 else "#d63031"
        irr_str = f"{dcf.irr:.1%}" if dcf.irr is not None else "N/A"
        payback_str = f"Month {dcf.discounted_payback_month}" if dcf.discounted_payback_month else "Never"
        dcf_cards = [
            ("💎", "Net Present Value", _fmt_inr(dcf.npv), npv_color),
            ("📈", "IRR (Annual)", irr_str, "#6c5ce7"),
            ("⏱️", "Payback Period", payback_str, "#0984e3"),
            ("🏗️", "Terminal Value", _fmt_inr(dcf.terminal_value), "#fdcb6e"),
        ]
        for col, (icon, label, value, accent) in zip(dcf_cols, dcf_cards):
            col.markdown(_card(icon, label, value, accent), unsafe_allow_html=True)
        st.write("")

        # PV cash flow chart
        st.subheader("Cumulative Present Value")
        pv_data = {"Cumulative PV (₹)": [r.cumulative_pv for r in dcf.monthly_dcf]}
        st.line_chart(pv_data, y_label="₹ (Present Value)", x_label="Month", height=300, use_container_width=True)

        with st.expander("Show DCF formulas"):
            r_m = (1 + sim_cfg.discount_rate_annual) ** (1/12) - 1
            st.markdown(f"**Annual discount rate** = {sim_cfg.discount_rate_annual:.1%}")
            st.markdown(f"**Monthly rate** = (1 + {sim_cfg.discount_rate_annual:.2f})^(1/12) − 1 = **{r_m:.6f}** ({r_m*100:.4f}%)")
            st.markdown(f"**NPV** = Σ CF_t / (1 + r)^t + TV = **{_fmt_inr(dcf.npv)}**")
            if dcf.irr is not None:
                st.markdown(f"**IRR** = rate where NPV = 0 → **{dcf.irr:.2%}** annual")
            st.markdown(f"**Terminal value method** = `{finance_cfg.terminal_value_method}`")
            st.markdown(f"**Undiscounted total CF** = {_fmt_inr(dcf.undiscounted_total)}")

        with st.expander("Monthly DCF table"):
            dcf_rows = []
            for r in dcf.monthly_dcf:
                dcf_rows.append({
                    "Month": r.month,
                    "Discount Factor": f"{r.discount_factor:.6f}",
                    "Nominal CF (₹)": f"₹{r.nominal_net_cf:,.0f}",
                    "PV CF (₹)": f"₹{r.pv_net_cf:,.0f}",
                    "Cumulative PV (₹)": f"₹{r.cumulative_pv:,.0f}",
                })
            st.dataframe(dcf_rows, use_container_width=True, hide_index=True, height=min(400, 35 * len(dcf_rows) + 38))

        # ── Debt Schedule ───────────────────────────────────────────────
        st.divider()
        st.subheader("Debt Schedule")

        if debt.loan_amount > 0:
            debt_cols = st.columns(4)
            debt_cards = [
                ("💰", "Loan Amount", _fmt_inr(debt.loan_amount), "#6c5ce7"),
                ("📊", "Monthly Interest Rate", f"{debt.monthly_rate*100:.3f}%", "#0984e3"),
                ("💸", "Total Interest Paid", _fmt_inr(debt.total_interest_paid), "#e17055"),
                ("🏗️", "Total Principal Paid", _fmt_inr(debt.total_principal_paid), "#00b894"),
            ]
            for col, (icon, label, value, accent) in zip(debt_cols, debt_cards):
                col.markdown(_card(icon, label, value, accent), unsafe_allow_html=True)
            st.write("")

            with st.expander("Show debt formulas"):
                st.markdown(f"**Loan** = CapEx × debt_pct = {_fmt_inr(total_capex)} × {finance_cfg.debt_pct_of_capex:.0%} = **{_fmt_inr(debt.loan_amount)}**")
                st.markdown(f"**Monthly rate** = {finance_cfg.interest_rate_annual:.1%} / 12 = **{debt.monthly_rate*100:.3f}%**")
                st.markdown(f"**Grace period** = {finance_cfg.grace_period_months} months (interest-only)")
                amort = finance_cfg.loan_tenor_months - finance_cfg.grace_period_months
                st.markdown(f"**Amortization** = {finance_cfg.loan_tenor_months} − {finance_cfg.grace_period_months} = **{amort} months**")
                if debt.rows:
                    emi = debt.rows[finance_cfg.grace_period_months].emi if len(debt.rows) > finance_cfg.grace_period_months else 0
                    st.markdown(f"**EMI** = P × r × (1+r)^n / ((1+r)^n − 1) = **{_fmt_inr(emi)}/month**")

            # EMI waterfall chart
            emi_int = [r.interest for r in debt.rows]
            emi_prin = [r.principal for r in debt.rows]
            st.subheader("EMI Breakdown")
            emi_chart = {"Interest": emi_int, "Principal": emi_prin}
            st.bar_chart(emi_chart, y_label="₹", x_label="Month", height=280, use_container_width=True,
                         color=["#e17055", "#00b894"], stack=True)

            with st.expander("Amortization schedule"):
                debt_rows_display = []
                for r in debt.rows:
                    debt_rows_display.append({
                        "Month": r.month,
                        "Opening (₹)": f"₹{r.opening_balance:,.0f}",
                        "Interest (₹)": f"₹{r.interest:,.0f}",
                        "Principal (₹)": f"₹{r.principal:,.0f}",
                        "EMI (₹)": f"₹{r.emi:,.0f}",
                        "Closing (₹)": f"₹{r.closing_balance:,.0f}",
                    })
                st.dataframe(debt_rows_display, use_container_width=True, hide_index=True, height=min(400, 35 * len(debt_rows_display) + 38))
        else:
            st.info("No debt configured (debt % = 0). The project is fully equity-funded.")

        # ── DSCR ────────────────────────────────────────────────────────
        st.divider()
        st.subheader("Debt Service Coverage Ratio")

        if debt.loan_amount > 0:
            dscr_cols = st.columns(4)
            min_dscr_color = "#00b894" if dscr.min_dscr >= finance_cfg.dscr_covenant_threshold else "#d63031"
            avg_dscr_color = "#00b894" if dscr.avg_dscr >= finance_cfg.dscr_covenant_threshold else "#d63031"
            dscr_cards = [
                ("📊", "Average DSCR", f"{dscr.avg_dscr:.2f}×", avg_dscr_color),
                ("📉", "Minimum DSCR", f"{dscr.min_dscr:.2f}× (Mo. {dscr.min_dscr_month})", min_dscr_color),
                ("⚠️", "Covenant Threshold", f"{dscr.covenant_threshold:.2f}×", "#fdcb6e"),
                ("🚨", "Covenant Breaches", f"{len(dscr.breach_months)}", "#d63031" if dscr.breach_months else "#00b894"),
            ]
            for col, (icon, label, value, accent) in zip(dscr_cols, dscr_cards):
                col.markdown(_card(icon, label, value, accent), unsafe_allow_html=True)
            st.write("")

            if dscr.asset_cover_ratio is not None:
                st.metric("Asset Cover Ratio", f"{dscr.asset_cover_ratio:.2f}×",
                          help="Remaining asset value ÷ outstanding loan balance at horizon end")

            # DSCR chart
            import math as _math
            finite_dscr = [d if not _math.isinf(d) else None for d in dscr.monthly_dscr]
            dscr_chart = {"DSCR": finite_dscr}
            st.line_chart(dscr_chart, y_label="DSCR", x_label="Month", height=280, use_container_width=True)
            st.caption(f"Red zone = DSCR < {finance_cfg.dscr_covenant_threshold:.2f}× covenant threshold")

            with st.expander("Show DSCR formula"):
                st.markdown("**DSCR** = Net Operating Income / Debt Service")
                st.markdown("**NOI** = Revenue − OpEx (before CapEx & debt service)")
                st.markdown("**Debt Service** = Interest + Principal (EMI)")
                if dscr.breach_months:
                    st.error(f"⚠️ **{len(dscr.breach_months)} breach months**: {dscr.breach_months[:10]}{'...' if len(dscr.breach_months) > 10 else ''}")
                else:
                    st.success("✅ No DSCR covenant breaches — SLB-ready.")
        else:
            st.info("DSCR not applicable — no debt configured.")

        # ── P&L Statement ───────────────────────────────────────────────
        st.divider()
        st.subheader("Profit & Loss Statement")

        # EBITDA timeline
        ebitda_data = {"EBITDA": [r.ebitda for r in stmts.pnl], "Net Income": [r.net_income for r in stmts.pnl]}
        st.line_chart(ebitda_data, y_label="₹", x_label="Month", height=280, use_container_width=True)

        # Summary metrics
        total_revenue = sum(r.revenue for r in stmts.pnl)
        total_ebitda = sum(r.ebitda for r in stmts.pnl)
        total_net_income = sum(r.net_income for r in stmts.pnl)
        total_tax = sum(r.tax for r in stmts.pnl)
        pnl_cols = st.columns(4)
        pnl_cards = [
            ("📈", "Cumulative Revenue", _fmt_inr(total_revenue), "#00b894"),
            ("💰", "Cumulative EBITDA", _fmt_inr(total_ebitda), "#6c5ce7"),
            ("💸", "Cumulative Tax", _fmt_inr(total_tax), "#e17055"),
            ("🎯", "Net Income", _fmt_inr(total_net_income), "#00b894" if total_net_income >= 0 else "#d63031"),
        ]
        for col, (icon, label, value, accent) in zip(pnl_cols, pnl_cards):
            col.markdown(_card(icon, label, value, accent), unsafe_allow_html=True)

        with st.expander("Monthly P&L detail"):
            pnl_rows = []
            for r in stmts.pnl:
                pnl_rows.append({
                    "Mo": r.month,
                    "Revenue": f"₹{r.revenue:,.0f}",
                    "Elec.": f"₹{r.electricity_cost:,.0f}",
                    "Labor": f"₹{r.labor_cost:,.0f}",
                    "Gross": f"₹{r.gross_profit:,.0f}",
                    "Stn OpEx": f"₹{r.station_opex:,.0f}",
                    "EBITDA": f"₹{r.ebitda:,.0f}",
                    "Deprec.": f"₹{r.depreciation:,.0f}",
                    "EBIT": f"₹{r.ebit:,.0f}",
                    "Interest": f"₹{r.interest:,.0f}",
                    "EBT": f"₹{r.ebt:,.0f}",
                    "Tax": f"₹{r.tax:,.0f}",
                    "Net Inc.": f"₹{r.net_income:,.0f}",
                })
            st.dataframe(pnl_rows, use_container_width=True, hide_index=True, height=min(400, 35 * len(pnl_rows) + 38))

        with st.expander("Show P&L formulas"):
            st.markdown("**Gross Profit** = Revenue − Electricity − Labor")
            st.markdown("**EBITDA** = Gross Profit − Station OpEx")
            st.markdown("**EBIT** = EBITDA − Depreciation")
            st.markdown("**EBT** = EBIT − Interest")
            st.markdown("**Net Income** = EBT − Tax (tax only on positive EBT)")
            st.markdown(f"**Depreciation method** = `{finance_cfg.depreciation_method}`, asset life = {finance_cfg.asset_useful_life_months} months")
            st.markdown(f"**Tax rate** = {finance_cfg.tax_rate:.0%}")

        # ── Cash Flow Statement ─────────────────────────────────────────
        st.divider()
        st.subheader("Cash Flow Statement")

        cf_op = [r.operating_cf for r in stmts.cash_flow]
        cf_inv = [r.investing_cf for r in stmts.cash_flow]
        cf_fin = [r.financing_cf for r in stmts.cash_flow]
        cf_cum = [r.cumulative_cf for r in stmts.cash_flow]

        st.subheader("Cumulative Cash Flow (Financed)")
        st.line_chart({"Cumulative CF (financed)": cf_cum}, y_label="₹", x_label="Month", height=280, use_container_width=True)

        total_op = sum(cf_op)
        total_inv = sum(cf_inv)
        total_fin = sum(cf_fin)
        cf_cols = st.columns(4)
        cf_cards = [
            ("🔄", "Operating Cash Flow", _fmt_inr(total_op), "#00b894"),
            ("🏗️", "Investing Cash Flow", _fmt_inr(total_inv), "#0984e3"),
            ("🏦", "Financing Cash Flow", _fmt_inr(total_fin), "#6c5ce7"),
            ("💎", "Net Cash Flow", _fmt_inr(total_op + total_inv + total_fin), "#00b894" if (total_op + total_inv + total_fin) >= 0 else "#d63031"),
        ]
        for col, (icon, label, value, accent) in zip(cf_cols, cf_cards):
            col.markdown(_card(icon, label, value, accent), unsafe_allow_html=True)

        with st.expander("Monthly cash flow detail"):
            cfs_rows = []
            for r in stmts.cash_flow:
                cfs_rows.append({
                    "Mo": r.month,
                    "Operating (₹)": f"₹{r.operating_cf:,.0f}",
                    "Investing (₹)": f"₹{r.investing_cf:,.0f}",
                    "Financing (₹)": f"₹{r.financing_cf:,.0f}",
                    "Net CF (₹)": f"₹{r.net_cf:,.0f}",
                    "Cumulative (₹)": f"₹{r.cumulative_cf:,.0f}",
                })
            st.dataframe(cfs_rows, use_container_width=True, hide_index=True, height=min(400, 35 * len(cfs_rows) + 38))

        with st.expander("Show cash flow formulas"):
            st.markdown("**Operating CF** = Revenue − Cash OpEx (no depreciation)")
            st.markdown("**Investing CF** = −CapEx (station + charger + packs + replacements)")
            st.markdown("**Financing CF** = Debt drawdown (month 1) − EMI repayments")
            st.markdown("**Net CF** = Operating + Investing + Financing")

        # ── Charger NPV Comparison ──────────────────────────────────────
        st.divider()
        st.subheader("Charger TCO Comparison (NPV)")

        cnpv_results = []
        for res in results:
            cv = next(c for c in charger_variants if c.name == res.charger_variant_id)
            cnpv = compute_charger_npv(cv, res.charger_tco, res.derived, sim_cfg, station)
            cnpv_results.append((cv, cnpv))

        if len(cnpv_results) > 1:
            # Comparison table
            cnpv_rows = []
            for cv, cnpv in cnpv_results:
                cnpv_rows.append({
                    "Charger": cnpv.charger_name,
                    "Undiscounted TCO": _fmt_inr(cnpv.undiscounted_tco),
                    "NPV(TCO)": _fmt_inr(cnpv.npv_tco),
                    "PV(Purchase)": _fmt_inr(cnpv.pv_purchase),
                    "PV(Repairs)": _fmt_inr(cnpv.pv_repairs),
                    "PV(Replacements)": _fmt_inr(cnpv.pv_replacements),
                    "PV(Lost Rev)": _fmt_inr(cnpv.pv_lost_revenue),
                    "Disc. CPC (₹)": f"₹{cnpv.discounted_cpc:.4f}",
                })
            st.dataframe(cnpv_rows, use_container_width=True, hide_index=True)

            best_cnpv = min(cnpv_results, key=lambda x: x[1].npv_tco)
            st.success(f"✅ **{best_cnpv[1].charger_name}** has the lowest discounted TCO at **{_fmt_inr(best_cnpv[1].npv_tco)}** (NPV).")

            # Discounted CPC trajectory
            st.subheader("Discounted Cost per Cycle Trend")
            dcpc_chart = {}
            for cv, cnpv in cnpv_results:
                dcpc_chart[cnpv.charger_name] = cnpv.monthly_discounted_cpc
            st.line_chart(dcpc_chart, y_label="₹ / cycle (discounted)", x_label="Month", height=280, use_container_width=True)
        else:
            cv, cnpv = cnpv_results[0]
            cnpv_cols = st.columns(4)
            cnpv_cards = [
                ("💰", "NPV of Total Cost", _fmt_inr(cnpv.npv_tco), "#6c5ce7"),
                ("📊", "Discounted CPC", f"₹{cnpv.discounted_cpc:.4f}", "#0984e3"),
                ("🔧", "PV of Repairs", _fmt_inr(cnpv.pv_repairs), "#e17055"),
                ("♻️", "PV of Replacements", _fmt_inr(cnpv.pv_replacements), "#fdcb6e"),
            ]
            for col, (icon, label, value, accent) in zip(cnpv_cols, cnpv_cards):
                col.markdown(_card(icon, label, value, accent), unsafe_allow_html=True)
            st.write("")

            with st.expander("Show charger NPV formulas"):
                st.markdown(f"**NPV(TCO)** = PV(purchase) + PV(repairs) + PV(replacements) + PV(lost_rev) + PV(spares)")
                st.markdown(f"= {_fmt_inr(cnpv.pv_purchase)} + {_fmt_inr(cnpv.pv_repairs)} + {_fmt_inr(cnpv.pv_replacements)} + {_fmt_inr(cnpv.pv_lost_revenue)} + {_fmt_inr(cnpv.pv_spares)} = **{_fmt_inr(cnpv.npv_tco)}**")
                st.markdown(f"**Discounted CPC** = NPV(TCO) / PV(cycles_served) = **₹{cnpv.discounted_cpc:.4f}**")

    # ── Render per charger variant ──────────────────────────────────────
    if multi_charger:
        fin_tabs = st.tabs([r.charger_variant_id for r in results])
        for fin_tab, res in zip(fin_tabs, results):
            cv = next(c for c in charger_variants if c.name == res.charger_variant_id)
            with fin_tab:
                _render_finance_block(res, cv)
    else:
        cv0 = next(c for c in charger_variants if c.name == results[0].charger_variant_id)
        _render_finance_block(results[0], cv0)


# ═══════════════════════════════════════════════════════════════════════════
# ==================  INTELLIGENCE TAB  ====================================
# ═══════════════════════════════════════════════════════════════════════════
with intelligence_tab:

    st.divider()
    st.header("Pilot Sizing Optimizer")
    st.caption("Find the minimum fleet size to achieve your financial target")

    # ── Pilot sizing controls ─────────────────────────────────────────
    ps_cols = st.columns([1, 1, 1, 1])
    _TARGET_OPTS = ["positive_npv", "positive_ncf", "break_even_within"]
    _TARGET_LABELS = {
        "positive_npv": "Positive NPV",
        "positive_ncf": "Positive Net Cash Flow",
        "break_even_within": "Break-even within N months",
    }
    ps_target = ps_cols[0].selectbox(
        "Target metric", _TARGET_OPTS,
        format_func=lambda x: _TARGET_LABELS[x],
        key="ps_target",
    )
    ps_confidence = ps_cols[1].number_input(
        "Confidence %", 10.0, 99.0, 50.0, 10.0,
        key="ps_conf",
        help="For stochastic: 50 = median must pass, 90 = P10 must pass",
    )
    ps_min = ps_cols[2].number_input("Min fleet", 10, 10000, 10, 10, key="ps_min")
    ps_max = ps_cols[3].number_input("Max fleet", 50, 50000, 2000, 100, key="ps_max")

    ps_extra_cols = st.columns([1, 1, 2])
    ps_be_target = ps_extra_cols[0].number_input(
        "Break-even target (months)", 6, 240, sim_cfg.horizon_months, 6,
        key="ps_be", disabled=(ps_target != "break_even_within"),
    )
    ps_max_iter = ps_extra_cols[1].number_input(
        "Max search steps", 3, 30, 15, 1, key="ps_iter",
    )
    ps_charger_idx = 0
    if multi_charger:
        ps_charger_idx = ps_extra_cols[2].selectbox(
            "Charger variant", range(len(charger_variants)),
            format_func=lambda i: charger_variants[i].name,
            key="ps_cv",
        )

    _ps_mode_cols = st.columns(2)
    ps_run_binary = _ps_mode_cols[0].button(
        "🔍  Binary Search (min fleet)", type="primary", key="ps_run_bin",
    )
    ps_run_eval = _ps_mode_cols[1].button(
        "📊  Evaluate Specific Sizes", key="ps_run_eval",
    )

    if ps_run_binary:
        with st.spinner("Searching for minimum viable fleet size…"):
            ps_result = find_minimum_fleet_size(
                scenario, charger_variants[ps_charger_idx],
                target_metric=ps_target,
                target_confidence_pct=ps_confidence,
                min_fleet=ps_min, max_fleet=ps_max,
                max_iterations=ps_max_iter,
                break_even_target_months=ps_be_target if ps_target == "break_even_within" else None,
            )
        st.session_state["ps_result"] = ps_result

    if ps_run_eval:
        # Build fleet sizes to evaluate: from min to max in 5–8 steps
        _step = max(1, (ps_max - ps_min) // 7)
        _fleet_sizes = list(range(ps_min, ps_max + 1, _step))
        if ps_max not in _fleet_sizes:
            _fleet_sizes.append(ps_max)
        with st.spinner(f"Evaluating {len(_fleet_sizes)} fleet sizes…"):
            ps_result = find_optimal_scale(
                scenario, charger_variants[ps_charger_idx],
                fleet_sizes=_fleet_sizes,
                target_metric=ps_target,
                target_confidence_pct=ps_confidence,
            )
        st.session_state["ps_result"] = ps_result

    if "ps_result" in st.session_state:
        psr = st.session_state["ps_result"]

        if psr.achieved:
            st.success(f"✅ Target achievable! Recommended fleet: **{psr.recommended_fleet_size:,} vehicles**")
        else:
            st.warning(f"⚠️ Target not achievable within search range ({ps_min:,}–{ps_max:,} vehicles)")

        ps_card_cols = st.columns(4)
        ps_cards = [
            ("🚗", "Recommended Fleet Size", f"{psr.recommended_fleet_size:,}", "#6c5ce7"),
            ("💎", "Projected NPV", _fmt_inr(psr.best_npv) if psr.best_npv is not None else "N/A",
             "#00b894" if psr.best_npv and psr.best_npv > 0 else "#d63031"),
            ("⏱️", "Break-even Month", f"Mo. {psr.best_break_even_month}" if psr.best_break_even_month else "Never", "#0984e3"),
            ("📊", "Monthly Net CF", _fmt_inr(psr.best_monthly_ncf_at_target) if psr.best_monthly_ncf_at_target else "N/A", "#fdcb6e"),
        ]
        for col, (icon, label, value, accent) in zip(ps_card_cols, ps_cards):
            col.markdown(_card(icon, label, value, accent), unsafe_allow_html=True)
        st.write("")

        st.markdown(f"**Search iterations**: {psr.search_iterations} · "
                    f"**Target**: {_TARGET_LABELS.get(psr.target_metric, psr.target_metric)} · "
                    f"**Confidence**: {psr.target_confidence_pct:.0f}%")

        if psr.search_log:
            with st.expander(f"Search log ({len(psr.search_log)} evaluations)"):
                log_rows = []
                for entry in psr.search_log:
                    npv_val = entry.get("npv")
                    ncf_val = entry.get("ncf")
                    log_rows.append({
                        "Fleet Size": entry["fleet_size"],
                        "NPV": _fmt_inr(npv_val) if npv_val is not None else "N/A",
                        "NCF": _fmt_inr(ncf_val) if ncf_val is not None else "N/A",
                        "Break-even": f"Mo. {entry['break_even_month']}" if entry.get("break_even_month") else "Never",
                        "Passed": "✅" if entry.get("passed") else "❌",
                    })
                st.dataframe(log_rows, use_container_width=True, hide_index=True)

            # NPV vs fleet size chart
            fleet_sizes_log = [e["fleet_size"] for e in psr.search_log]
            npvs_log = [e.get("npv", 0) or 0 for e in psr.search_log]
            if len(fleet_sizes_log) > 1:
                # Sort by fleet size for chart
                sorted_pairs = sorted(zip(fleet_sizes_log, npvs_log))
                st.subheader("NPV vs Fleet Size")
                chart_data = {"NPV (₹)": [p[1] for p in sorted_pairs]}
                st.bar_chart(chart_data, y_label="NPV (₹)", x_label="Fleet Size", height=280,
                             use_container_width=True)
                st.caption("Fleet sizes evaluated: " + ", ".join(str(p[0]) for p in sorted_pairs))

        with st.expander("Show methodology"):
            st.markdown("""
**Binary search**: Finds the *minimum* fleet size in `[min, max]` that meets the target.
Each step evaluates the midpoint fleet size by running a full simulation + DCF.

**Evaluate specific sizes**: Runs simulations at evenly-spaced fleet sizes and picks
the one with the highest NPV that meets the target.

**Confidence levels** (stochastic engine only):
- 50% → P50 (median) must meet the target
- 90% → P10 (pessimistic end) must meet the target — conservative for investors
- Static engine ignores confidence (deterministic result)

**Target metrics**:
- **Positive NPV**: Discounted cash flows yield NPV > 0
- **Positive NCF**: Total (undiscounted) net cash flow > 0
- **Break-even within**: Project breaks even within N months
""")

    # ── SECTION 2 — Field Data Upload ──────────────────────────────────
    st.divider()
    st.header("Field Data Upload")
    st.caption("Upload real-world BMS telemetry and charger failure logs to compare against model predictions")

    fd_col1, fd_col2 = st.columns(2)

    with fd_col1:
        st.subheader("BMS Telemetry")
        st.markdown("""
        <div style="font-family: 'Inter', sans-serif; font-size: 0.72rem; color: rgba(255,255,255,0.40); margin-bottom: 6px; line-height: 1.5;">
        Required: <code>pack_id, month, soh, cumulative_cycles</code><br>
        Optional: <code>temperature_avg_c</code>
        </div>
        """, unsafe_allow_html=True)
        bms_file = st.file_uploader("Upload BMS CSV", type=["csv"], key="bms_upload")

    with fd_col2:
        st.subheader("Charger Failure Log")
        st.markdown("""
        <div style="font-family: 'Inter', sans-serif; font-size: 0.72rem; color: rgba(255,255,255,0.40); margin-bottom: 6px; line-height: 1.5;">
        Required: <code>dock_id, failure_month, downtime_hours</code><br>
        Optional: <code>charger_variant_name, repair_cost, was_replaced</code>
        </div>
        """, unsafe_allow_html=True)
        charger_file = st.file_uploader("Upload Charger CSV", type=["csv"], key="charger_upload")

    # Parse uploaded files
    bms_records = []
    charger_fail_records = []

    if bms_file is not None:
        bms_content = bms_file.getvalue().decode("utf-8")
        bms_records = ingest_bms_csv(io.StringIO(bms_content))

    if charger_file is not None:
        charger_content = charger_file.getvalue().decode("utf-8")
        charger_fail_records = ingest_charger_csv(io.StringIO(charger_content))

    field_data = FieldDataSet(bms_records=bms_records, charger_failure_records=charger_fail_records)

    has_field_data = len(bms_records) > 0 or len(charger_fail_records) > 0

    if has_field_data:
        # Data summary cards
        fd_summary_cols = st.columns(4)
        fd_cards = [
            ("🔋", "BMS Records", f"{len(bms_records):,}", "#6c5ce7"),
            ("📦", "Unique Packs", f"{field_data.num_unique_packs:,}", "#0984e3"),
            ("⚡", "Failure Events", f"{len(charger_fail_records):,}", "#e17055"),
            ("📅", "Data Span", f"{field_data.max_month} mo.", "#fdcb6e"),
        ]
        for col, (icon, label, value, accent) in zip(fd_summary_cols, fd_cards):
            col.markdown(_card(icon, label, value, accent), unsafe_allow_html=True)
        st.write("")

        # Preview data
        if bms_records:
            with st.expander(f"BMS data preview ({len(bms_records)} records)"):
                bms_preview = [{
                    "Pack": r.pack_id, "Month": r.month,
                    "SOH": f"{r.soh:.3f}", "Cycles": r.cumulative_cycles,
                    "Temp (°C)": f"{r.temperature_avg_c:.1f}" if r.temperature_avg_c else "—",
                } for r in bms_records[:50]]
                st.dataframe(bms_preview, use_container_width=True, hide_index=True)
                if len(bms_records) > 50:
                    st.caption(f"Showing first 50 of {len(bms_records)} records.")

        if charger_fail_records:
            with st.expander(f"Charger failure preview ({len(charger_fail_records)} events)"):
                cf_preview = [{
                    "Dock": r.dock_id, "Month": r.failure_month,
                    "Downtime (hrs)": f"{r.downtime_hours:.1f}",
                    "Variant": r.charger_variant_name or "—",
                    "Repair ₹": f"₹{r.repair_cost:,.0f}" if r.repair_cost else "—",
                    "Replaced": "Yes" if r.was_replaced else "No",
                } for r in charger_fail_records[:50]]
                st.dataframe(cf_preview, use_container_width=True, hide_index=True)
                if len(charger_fail_records) > 50:
                    st.caption(f"Showing first 50 of {len(charger_fail_records)} events.")

        # ── Variance Analysis ─────────────────────────────────────────
        st.divider()
        st.header("Model vs Reality")

        fd_charger_idx = 0
        if multi_charger:
            fd_charger_idx = st.selectbox(
                "Charger variant for analysis", range(len(charger_variants)),
                format_func=lambda i: charger_variants[i].name,
                key="fd_cv",
            )

        cv_for_fd = charger_variants[fd_charger_idx]
        variance_report = compute_variance_report(
            field_data, pack, cv_for_fd, chaos_cfg, station,
        )

        # Degradation variance
        if variance_report.degradation_monthly:
            st.subheader("Battery SOH — Model vs Field")

            drift_color = "#00b894" if variance_report.overall_soh_drift_pct and variance_report.overall_soh_drift_pct >= 0 else "#d63031"
            var_cols = st.columns(3)
            var_cards = [
                ("📊", "SOH Drift",
                 f"{variance_report.overall_soh_drift_pct:+.2f}%" if variance_report.overall_soh_drift_pct is not None else "N/A",
                 drift_color),
                ("🔋", "Data Months", f"{len(variance_report.degradation_monthly)}", "#0984e3"),
                ("📦", "Packs Sampled", f"{variance_report.degradation_monthly[0].num_packs_sampled:,}", "#6c5ce7"),
            ]
            for col, (icon, label, value, accent) in zip(var_cols, var_cards):
                col.markdown(_card(icon, label, value, accent), unsafe_allow_html=True)
            st.write("")

            if variance_report.overall_soh_drift_pct is not None:
                if variance_report.overall_soh_drift_pct < -5:
                    st.error("⚠️ Field data shows batteries degrading **faster** than the model predicts. Consider increasing β.")
                elif variance_report.overall_soh_drift_pct > 5:
                    st.success("✅ Field batteries are healthier than predicted — model is conservative.")
                else:
                    st.info("ℹ️ Field data closely matches model predictions (within ±5%).")

            # SOH comparison chart
            projected_soh = {dv.month: dv.projected_avg_soh for dv in variance_report.degradation_monthly}
            actual_soh = {dv.month: dv.actual_avg_soh for dv in variance_report.degradation_monthly}
            all_months = sorted(projected_soh.keys())
            soh_chart = {
                "Projected SOH": [projected_soh[m] for m in all_months],
                "Actual SOH": [actual_soh[m] for m in all_months],
            }
            st.line_chart(soh_chart, y_label="State of Health", x_label="Month", height=300,
                          use_container_width=True)

            with st.expander("Degradation variance detail"):
                deg_rows = [{
                    "Month": dv.month,
                    "Projected SOH": f"{dv.projected_avg_soh:.4f}",
                    "Actual SOH": f"{dv.actual_avg_soh:.4f}",
                    "Variance": f"{dv.variance_pct:+.2f}%",
                    "Packs Sampled": dv.num_packs_sampled,
                } for dv in variance_report.degradation_monthly]
                st.dataframe(deg_rows, use_container_width=True, hide_index=True)

            with st.expander("Show degradation formula"):
                st.markdown(f"**Model**: SOH = 1.0 − β × cycles − calendar × months")
                st.markdown(f"**β** = {pack.cycle_degradation_rate_pct}% / cycle × aggressiveness ({chaos_cfg.aggressiveness_index})")
                st.markdown(f"**Calendar aging** = {pack.calendar_aging_rate_pct_per_month}% / month")
                st.markdown(f"**Variance** = (actual − projected) / projected × 100")

        # MTBF variance
        if variance_report.mtbf_variance:
            st.subheader("Charger Reliability — Spec vs Field")

            mtbf_drift_color = "#00b894" if variance_report.overall_mtbf_drift_pct and variance_report.overall_mtbf_drift_pct >= 0 else "#d63031"
            mtbf_cols = st.columns(3)
            mv = variance_report.mtbf_variance[0]
            mtbf_cards = [
                ("📊", "MTBF Drift",
                 f"{variance_report.overall_mtbf_drift_pct:+.2f}%" if variance_report.overall_mtbf_drift_pct is not None else "N/A",
                 mtbf_drift_color),
                ("🛠️", "Rated MTBF", f"{mv.projected_mtbf_hours:,.0f} hrs", "#0984e3"),
                ("📈", "Observed MTBF", f"{mv.actual_mtbf_hours:,.0f} hrs", "#6c5ce7"),
            ]
            for col, (icon, label, value, accent) in zip(mtbf_cols, mtbf_cards):
                col.markdown(_card(icon, label, value, accent), unsafe_allow_html=True)
            st.write("")

            if variance_report.overall_mtbf_drift_pct is not None:
                if variance_report.overall_mtbf_drift_pct < -20:
                    st.error("⚠️ Chargers failing **more frequently** than spec. Actual MTBF is significantly below rated.")
                elif variance_report.overall_mtbf_drift_pct > 20:
                    st.success("✅ Chargers outperforming spec — actual MTBF exceeds rated value.")
                else:
                    st.info("ℹ️ Charger failure rate is within ±20% of spec.")

            with st.expander("MTBF variance detail"):
                mtbf_rows = [{
                    "Variant": mv.charger_variant_name or "Fleet",
                    "Spec MTBF": f"{mv.projected_mtbf_hours:,.0f} hrs",
                    "Actual MTBF": f"{mv.actual_mtbf_hours:,.0f} hrs",
                    "Variance": f"{mv.variance_pct:+.2f}%",
                    "Total Op. Hours": f"{mv.total_operating_hours:,.0f}",
                    "Failures": mv.total_failures,
                } for mv in variance_report.mtbf_variance]
                st.dataframe(mtbf_rows, use_container_width=True, hide_index=True)

            with st.expander("Show MTBF formula"):
                st.markdown("**Actual MTBF** = total_operating_hours / total_failures")
                st.markdown(f"**Total operating hours** = unique_docks × hours/day × 30 × months")
                st.markdown(f"**Variance** = (actual − projected) / projected × 100")

        if not variance_report.degradation_monthly and not variance_report.mtbf_variance:
            st.info("No variance data to display. Upload field data above to compare against model predictions.")

        # ── Auto-Tuning ───────────────────────────────────────────────
        st.divider()
        st.header("Auto-Calibration")
        st.caption("Adjust model parameters based on field observations")

        at_cols = st.columns(2)
        at_min_conf = at_cols[0].slider(
            "Min confidence threshold", 0.0, 1.0, 0.1, 0.05,
            key="at_conf",
            help="Parameters with confidence below this threshold are excluded. "
                 "Confidence is based on sample size (packs ÷ 50, failures ÷ 10).",
        )
        at_run = at_cols[1].button("🔧  Run Auto-Tune", type="primary", key="at_run")

        if at_run:
            with st.spinner("Auto-tuning parameters from field data…"):
                tune_result = auto_tune_parameters(
                    field_data, scenario, cv_for_fd, min_confidence=at_min_conf,
                )
            st.session_state["tune_result"] = tune_result

        if "tune_result" in st.session_state:
            tune = st.session_state["tune_result"]

            tune_info_cols = st.columns(3)
            tune_info_cards = [
                ("📅", "Data Months Used", f"{tune.data_months_used}", "#6c5ce7"),
                ("📦", "Packs Sampled", f"{tune.num_packs_used:,}", "#0984e3"),
                ("⚡", "Failure Events", f"{tune.num_failure_events_used:,}", "#e17055"),
            ]
            for col, (icon, label, value, accent) in zip(tune_info_cols, tune_info_cards):
                col.markdown(_card(icon, label, value, accent), unsafe_allow_html=True)
            st.write("")

            if tune.parameters:
                st.subheader("Tuned Parameters")
                tune_rows = []
                for tp in tune.parameters:
                    direction = "↑" if tp.change_pct > 0 else "↓"
                    conf_bar = "█" * int(tp.confidence * 10) + "░" * (10 - int(tp.confidence * 10))
                    tune_rows.append({
                        "Parameter": tp.param_path,
                        "Original": f"{tp.original_value:.4g}",
                        "Tuned": f"{tp.tuned_value:.4g}",
                        "Change": f"{direction} {tp.change_pct:+.1f}%",
                        "Confidence": f"{conf_bar} {tp.confidence:.0%}",
                    })
                st.dataframe(tune_rows, use_container_width=True, hide_index=True)

                # Apply tuned parameters button
                if st.button("✅  Apply Tuned Parameters & Re-run", type="primary", key="at_apply"):
                    with st.spinner("Applying tuned parameters and re-running simulation…"):
                        tuned_scenario, tuned_charger = apply_tuned_parameters(
                            scenario, cv_for_fd, tune,
                        )
                        tuned_result = run_engine(tuned_scenario, tuned_charger)

                        # Compute NPVs for comparison
                        orig_result = results[fd_charger_idx]
                        orig_salvage = orig_result.derived.total_packs * p.second_life_salvage_value
                        orig_dcf = build_dcf_table(
                            orig_result.months, orig_result.summary, finance_cfg,
                            sim_cfg.discount_rate_annual, orig_salvage,
                        )

                        tuned_salvage = tuned_result.derived.total_packs * tuned_scenario.pack.second_life_salvage_value
                        tuned_dcf = build_dcf_table(
                            tuned_result.months, tuned_result.summary, tuned_scenario.finance,
                            tuned_scenario.simulation.discount_rate_annual, tuned_salvage,
                        )

                    st.session_state["tuned_comparison"] = {
                        "original_npv": orig_dcf.npv,
                        "tuned_npv": tuned_dcf.npv,
                        "original_ncf": orig_result.summary.total_net_cash_flow,
                        "tuned_ncf": tuned_result.summary.total_net_cash_flow,
                        "original_be": orig_result.summary.break_even_month,
                        "tuned_be": tuned_result.summary.break_even_month,
                    }

                if "tuned_comparison" in st.session_state:
                    tc = st.session_state["tuned_comparison"]
                    st.subheader("Calibration Impact")

                    npv_delta = tc["tuned_npv"] - tc["original_npv"]
                    delta_color = "#00b894" if npv_delta >= 0 else "#d63031"
                    delta_dir = "better" if npv_delta >= 0 else "worse"

                    imp_cols = st.columns(3)
                    imp_cards = [
                        ("📊", "Original NPV", _fmt_inr(tc["original_npv"]),
                         "#6c5ce7"),
                        ("🔧", "Calibrated NPV", _fmt_inr(tc["tuned_npv"]),
                         "#00b894" if tc["tuned_npv"] > 0 else "#d63031"),
                        ("📈", "NPV Delta", f"{_fmt_inr(npv_delta)} ({delta_dir})",
                         delta_color),
                    ]
                    for col, (icon, label, value, accent) in zip(imp_cols, imp_cards):
                        col.markdown(_card(icon, label, value, accent), unsafe_allow_html=True)
                    st.write("")

                    comp_table = [
                        {
                            "Metric": "NPV",
                            "Original": _fmt_inr(tc["original_npv"]),
                            "Tuned": _fmt_inr(tc["tuned_npv"]),
                            "Delta": _fmt_inr(npv_delta),
                        },
                        {
                            "Metric": "Net Cash Flow",
                            "Original": _fmt_inr(tc["original_ncf"]),
                            "Tuned": _fmt_inr(tc["tuned_ncf"]),
                            "Delta": _fmt_inr(tc["tuned_ncf"] - tc["original_ncf"]),
                        },
                        {
                            "Metric": "Break-even",
                            "Original": f"Mo. {tc['original_be']}" if tc["original_be"] else "Never",
                            "Tuned": f"Mo. {tc['tuned_be']}" if tc["tuned_be"] else "Never",
                            "Delta": (
                                f"{tc['tuned_be'] - tc['original_be']:+d} months"
                                if tc["original_be"] and tc["tuned_be"]
                                else "N/A"
                            ),
                        },
                    ]
                    st.dataframe(comp_table, use_container_width=True, hide_index=True)

            else:
                st.info("No parameters met the confidence threshold. "
                        "Try lowering the threshold or uploading more field data.")

            with st.expander("Show calibration methodology"):
                st.markdown("""
**Degradation rate (β)**: For each BMS record, compute:
`β_eff = (1.0 − SOH − calendar_loss) / cumulative_cycles`, then take the median.

**Calendar aging**: For low-cycle packs (< 50 cycles), estimate:
`calendar_rate = (1.0 − SOH) / months`, then take the median.

**Charger MTBF**: From failure logs, compute:
`actual_MTBF = total_operating_hours / total_failures`

**Confidence scoring**:
- BMS: `min(1.0, num_packs / 50)` — 50+ packs = full confidence
- MTBF: `min(1.0, num_failures / 10)` — 10+ failures = full confidence
""")

    else:
        st.info("👆 Upload BMS and/or charger failure CSV files above to enable variance analysis and auto-tuning.")

    # ── Sample CSV templates ──────────────────────────────────────────
    st.divider()
    st.header("Download Templates")
    st.caption("Sample CSV templates as starting points for your field data")

    tmpl_cols = st.columns(2)
    with tmpl_cols[0]:
        bms_template = "pack_id,month,soh,cumulative_cycles,temperature_avg_c\nP001,6,0.95,300,35.2\nP001,12,0.89,620,34.0\nP002,6,0.94,310,36.0\nP002,12,0.88,650,33.5\n"
        st.download_button(
            "📥  Download BMS template CSV",
            data=bms_template,
            file_name="bms_telemetry_template.csv",
            mime="text/csv",
            key="dl_bms",
        )
    with tmpl_cols[1]:
        charger_template = "dock_id,failure_month,downtime_hours,charger_variant_name,repair_cost,was_replaced\nD01,3,8.5,Budget-1kW,1200,false\nD02,5,12.0,Budget-1kW,1500,false\nD01,9,24.0,Budget-1kW,2000,true\n"
        st.download_button(
            "📥  Download Charger Failure template CSV",
            data=charger_template,
            file_name="charger_failures_template.csv",
            mime="text/csv",
            key="dl_charger",
        )
