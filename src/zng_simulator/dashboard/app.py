"""ZNG BSN Simulator — Phase 1 Streamlit Dashboard.

Layout: sidebar inputs → main area outputs.
Design: metrics for headlines, proper tables, formulas in expanders,
two restrained visualisations (CPC bar, cumulative-CF line).
"""

from __future__ import annotations

import streamlit as st

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
from zng_simulator.engine.cashflow import run_simulation
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
/* ── Metric cards ─────────────────────────────────────────────────── */
div[data-testid="stMetric"] {
    background: linear-gradient(135deg, rgba(30,34,44,0.95), rgba(22,26,35,0.98));
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 12px;
    padding: 16px 20px 14px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.25);
}
div[data-testid="stMetric"] label {
    color: rgba(255,255,255,0.55) !important;
    font-size: 0.78rem !important;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
    font-size: 1.5rem !important;
    font-weight: 700 !important;
}

/* ── Section headers ──────────────────────────────────────────────── */
h1 { letter-spacing: -0.5px; }
h2 {
    border-left: 3px solid #6c5ce7;
    padding-left: 12px !important;
    margin-top: 0.5rem !important;
}
h3 {
    color: rgba(255,255,255,0.75) !important;
    font-weight: 500 !important;
    font-size: 1.05rem !important;
}

/* ── Expanders ────────────────────────────────────────────────────── */
details[data-testid="stExpander"] {
    background: rgba(30,34,44,0.6);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 10px;
}

/* ── Dataframe containers ─────────────────────────────────────────── */
div[data-testid="stDataFrame"] {
    border-radius: 10px;
    overflow: hidden;
}

/* ── Tabs ─────────────────────────────────────────────────────────── */
button[data-baseweb="tab"] {
    font-weight: 600 !important;
    letter-spacing: 0.3px;
}

/* ── Divider ──────────────────────────────────────────────────────── */
hr {
    border-color: rgba(255,255,255,0.06) !important;
    margin: 1.5rem 0 !important;
}

/* ── Sidebar polish ───────────────────────────────────────────────── */
section[data-testid="stSidebar"] > div {
    padding-top: 1.5rem;
}
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Title area
# ---------------------------------------------------------------------------
st.markdown("""
<div style="margin-bottom: 0.5rem;">
    <span style="font-size: 2rem; font-weight: 800; letter-spacing: -1px;">⚡ ZNG Battery Swap Network Simulator</span>
</div>
""", unsafe_allow_html=True)
st.caption("Phase 1 — Static Unit Economics · *Show the Math*")

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
        border: 1px solid rgba(255,255,255,0.06);
        border-top: 3px solid {accent};
        border-radius: 12px;
        padding: 18px 20px 14px;
        box-shadow: 0 2px 12px rgba(0,0,0,0.25);
        text-align: center;
    ">
        <div style="font-size: 1.6rem; margin-bottom: 4px;">{icon}</div>
        <div style="font-size: 1.5rem; font-weight: 700; color: #fff;">{value}</div>
        <div style="font-size: 0.75rem; color: rgba(255,255,255,0.5); text-transform: uppercase; letter-spacing: 0.5px; margin-top: 4px;">{label}</div>
    </div>
    """


# ---------------------------------------------------------------------------
# SIDEBAR — Inputs
# ---------------------------------------------------------------------------
st.sidebar.header("⚙️ Scenario Inputs")

# --- Vehicle ---
with st.sidebar.expander("🏍️ Vehicle Configuration", expanded=True):
    v_name = st.text_input("Vehicle name", _DEF_V.name)
    c1, c2 = st.columns(2)
    v_packs = c1.number_input("Packs / vehicle", 1, 4, _DEF_V.packs_per_vehicle)
    v_cap = c2.number_input("Pack capacity (kWh)", 0.1, 10.0, _DEF_V.pack_capacity_kwh, 0.01, format="%.2f")
    c1, c2 = st.columns(2)
    v_km = c1.number_input("Avg daily km", 1.0, 500.0, _DEF_V.avg_daily_km, 10.0)
    v_wh = c2.number_input("Wh / km", 1.0, 100.0, _DEF_V.energy_consumption_wh_per_km, 1.0)
    c1, c2 = st.columns(2)
    v_swap = c1.number_input("Swap time (min)", 0.5, 10.0, _DEF_V.swap_time_minutes, 0.5)
    v_buffer = c2.number_input("Range buffer %", 0, 50, int(_DEF_V.range_anxiety_buffer_pct * 100), 5)

vehicle = VehicleConfig(
    name=v_name, packs_per_vehicle=v_packs, pack_capacity_kwh=v_cap,
    avg_daily_km=v_km, energy_consumption_wh_per_km=v_wh,
    swap_time_minutes=v_swap, range_anxiety_buffer_pct=v_buffer / 100,
)

# --- Pack ---
_CHEM_OPTIONS = ["NMC", "LFP"]
with st.sidebar.expander("🔋 Battery Pack"):
    p_name = st.text_input("Pack name", _DEF_P.name)
    c1, c2 = st.columns(2)
    p_cap = c1.number_input("Capacity (kWh)", 0.1, 10.0, _DEF_P.nominal_capacity_kwh, 0.01, format="%.2f", key="p_cap")
    p_chem = c2.selectbox("Chemistry", _CHEM_OPTIONS, index=_CHEM_OPTIONS.index(_DEF_P.chemistry) if _DEF_P.chemistry in _CHEM_OPTIONS else 0)
    c1, c2 = st.columns(2)
    p_cost = c1.number_input("Cost (₹)", 0, 200000, int(_DEF_P.unit_cost), 1000)
    p_salvage = c2.number_input("Salvage (₹)", 0, 100000, int(_DEF_P.second_life_salvage_value), 500)
    c1, c2 = st.columns(2)
    p_beta = c1.number_input("β (%/cycle)", 0.001, 1.0, _DEF_P.cycle_degradation_rate_pct, 0.01, format="%.3f")
    p_retire = c2.number_input("Retire SOH %", 10, 100, int(_DEF_P.retirement_soh_pct * 100), 5)
    c1, c2 = st.columns(2)
    p_dod = c1.number_input("DoD %", 10, 100, int(_DEF_P.depth_of_discharge_pct * 100), 5)
    p_aggr = c2.number_input("Aggress. mult.", 0.1, 3.0, _DEF_P.aggressiveness_multiplier, 0.1)
    st.markdown("---\n**Pack Failure Model (MTBF)**")
    c1, c2 = st.columns(2)
    p_mtbf = c1.number_input("MTBF (hrs)", 1000, 500000, int(_DEF_P.mtbf_hours), 1000, key="p_mtbf")
    p_mttr = c2.number_input("MTTR (hrs)", 1, 200, int(_DEF_P.mttr_hours), 1, key="p_mttr")
    c1, c2 = st.columns(2)
    p_repair = c1.number_input("Repair ₹", 0, 50000, int(_DEF_P.repair_cost_per_event), 500, key="p_repair")
    p_thresh = c2.number_input("Replace after", 1, 10, _DEF_P.replacement_threshold, 1, key="p_thresh")
    c1, c2 = st.columns(2)
    p_repl = c1.number_input("Replace ₹", 0, 200000, int(_DEF_P.full_replacement_cost), 1000, key="p_repl")
    p_spare = c2.number_input("Spare/stn ₹", 0, 200000, int(_DEF_P.spare_packs_cost_per_station), 1000, key="p_spare")

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
with st.sidebar.expander("⚡ Charger Variants"):
    num_chargers = st.number_input("Variants to compare", 1, 5, 1)
    charger_variants: list[ChargerVariant] = []
    for i in range(num_chargers):
        st.markdown(f"---\n**Charger {i + 1}**")
        c_name = st.text_input("Name", f"Charger-{i+1}", key=f"cn_{i}")
        c1, c2 = st.columns(2)
        c_cost = c1.number_input("Cost/slot ₹", 0, 200000, int(_DEF_C.purchase_cost_per_slot), 1000, key=f"cc_{i}")
        c_power = c2.number_input("Power (W)", 100, 10000, int(_DEF_C.rated_power_w), 100, key=f"cp_{i}")
        c1, c2 = st.columns(2)
        c_eff = c1.number_input("Efficiency %", 50, 100, int(_DEF_C.charging_efficiency_pct * 100), 1, key=f"ce_{i}")
        c_mtbf = c2.number_input("MTBF (hrs)", 1000, 200000, int(_DEF_C.mtbf_hours), 1000, key=f"cm_{i}")
        c1, c2 = st.columns(2)
        c_mttr = c1.number_input("MTTR (hrs)", 1, 200, int(_DEF_C.mttr_hours), 4, key=f"cmt_{i}")
        c_repair = c2.number_input("Repair ₹", 0, 50000, int(_DEF_C.repair_cost_per_event), 500, key=f"cr_{i}")
        c1, c2 = st.columns(2)
        c_thresh = c1.number_input("Replace after", 1, 10, _DEF_C.replacement_threshold, 1, key=f"ct_{i}")
        c_repl = c2.number_input("Replace ₹", 0, 200000, int(_DEF_C.full_replacement_cost), 1000, key=f"crc_{i}")
        c_spare = st.number_input("Spare inv. ₹", 0, 200000, int(_DEF_C.spare_inventory_cost), 1000, key=f"cs_{i}")
        charger_variants.append(ChargerVariant(
            name=c_name, purchase_cost_per_slot=float(c_cost), rated_power_w=float(c_power),
            charging_efficiency_pct=c_eff / 100,
            efficiency_decay_pct_per_year=_DEF_C.efficiency_decay_pct_per_year,
            mtbf_hours=float(c_mtbf), mttr_hours=float(c_mttr),
            repair_cost_per_event=float(c_repair), replacement_threshold=c_thresh,
            full_replacement_cost=float(c_repl), spare_inventory_cost=float(c_spare),
            expected_useful_life_years=_DEF_C.expected_useful_life_years,
        ))

# --- Station ---
with st.sidebar.expander("🏢 Station & Infra"):
    c1, c2 = st.columns(2)
    s_num = c1.number_input("Stations", 1, 100, _DEF_S.num_stations, 1)
    s_docks = c2.number_input("Docks / stn", 1, 50, _DEF_S.docks_per_station, 1)
    s_hours = st.number_input("Op. hours/day", 1.0, 24.0, _DEF_S.operating_hours_per_day, 1.0)
    c1, c2 = st.columns(2)
    s_cab = c1.number_input("Cabinet ₹", 0, 500000, int(_DEF_S.cabinet_cost), 5000)
    s_site = c2.number_input("Site prep ₹", 0, 500000, int(_DEF_S.site_prep_cost), 5000)
    c1, c2 = st.columns(2)
    s_grid = c1.number_input("Grid conn. ₹", 0, 500000, int(_DEF_S.grid_connection_cost), 5000)
    s_sw = c2.number_input("Software ₹", 0, 1000000, int(_DEF_S.software_cost), 10000)
    s_dep = st.number_input("Security dep. ₹", 0, 500000, int(_DEF_S.security_deposit), 5000)

station = StationConfig(
    cabinet_cost=float(s_cab), site_prep_cost=float(s_site), grid_connection_cost=float(s_grid),
    software_cost=float(s_sw), security_deposit=float(s_dep), num_stations=s_num,
    docks_per_station=s_docks, operating_hours_per_day=s_hours,
)

# --- OpEx ---
with st.sidebar.expander("💰 OpEx"):
    o_tariff = st.number_input("Elec. tariff ₹/kWh", 0.0, 30.0, _DEF_O.electricity_tariff_per_kwh, 0.5)
    c1, c2 = st.columns(2)
    o_rent = c1.number_input("Rent/mo/stn ₹", 0, 200000, int(_DEF_O.rent_per_month_per_station), 1000)
    o_aux = c2.number_input("Aux power/mo ₹", 0, 50000, int(_DEF_O.auxiliary_power_per_month), 500)
    c1, c2 = st.columns(2)
    o_prev = c1.number_input("Prev. maint ₹", 0, 50000, int(_DEF_O.preventive_maintenance_per_month_per_station), 500)
    o_corr = c2.number_input("Corr. maint ₹", 0, 50000, int(_DEF_O.corrective_maintenance_per_month_per_station), 500)
    c1, c2 = st.columns(2)
    o_ins = c1.number_input("Insurance ₹", 0, 50000, int(_DEF_O.insurance_per_month_per_station), 500)
    o_log = c2.number_input("Logistics ₹", 0, 50000, int(_DEF_O.logistics_per_month_per_station), 1000)
    c1, c2 = st.columns(2)
    o_labor = c1.number_input("Labor/swap ₹", 0.0, 50.0, _DEF_O.pack_handling_labor_per_swap, 0.5)
    o_overhead = c2.number_input("Overhead/mo ₹", 0, 500000, int(_DEF_O.overhead_per_month), 5000)

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
with st.sidebar.expander("📈 Revenue"):
    r_price = st.number_input("₹ per swap visit", 0.0, 200.0, _DEF_R.price_per_swap, 5.0, help="Per vehicle visit, not per pack")
    c1, c2 = st.columns(2)
    r_fleet = c1.number_input("Init. fleet", 1, 100000, _DEF_R.initial_fleet_size, 50)
    r_add = c2.number_input("Monthly adds", 0, 5000, _DEF_R.monthly_fleet_additions, 10)

revenue_cfg = RevenueConfig(price_per_swap=r_price, initial_fleet_size=r_fleet, monthly_fleet_additions=r_add)

# --- Chaos ---
with st.sidebar.expander("🎲 Chaos & Risk"):
    c1, c2 = st.columns(2)
    ch_sab = c1.number_input("Sabotage %/mo", 0.0, 10.0, _DEF_CH.sabotage_pct_per_month * 100, 0.1, format="%.1f")
    ch_aggr = c2.number_input("Aggress. idx", 0.1, 3.0, _DEF_CH.aggressiveness_index, 0.1, key="ch_aggr")

chaos_cfg = ChaosConfig(sabotage_pct_per_month=ch_sab / 100, aggressiveness_index=ch_aggr, thermal_throttling_factor=1.0)

# --- Simulation ---
with st.sidebar.expander("🕐 Simulation"):
    sim_horizon = st.number_input("Horizon (months)", 6, 240, _DEF_SIM.horizon_months, 12)

sim_cfg = SimulationConfig(horizon_months=sim_horizon, discount_rate_annual=_DEF_SIM.discount_rate_annual)

# --- Build scenario & run ---
scenario = Scenario(
    vehicle=vehicle, pack=pack, charger_variants=charger_variants,
    station=station, opex=opex_cfg, revenue=revenue_cfg, chaos=chaos_cfg, simulation=sim_cfg,
)

run_clicked = st.sidebar.button("▶  Run Simulation", type="primary", use_container_width=True)

if not (run_clicked or "results" in st.session_state):
    st.markdown("""
    <div style="
        background: linear-gradient(135deg, rgba(108,92,231,0.15), rgba(9,132,227,0.10));
        border: 1px solid rgba(108,92,231,0.25);
        border-radius: 14px;
        padding: 40px 30px;
        text-align: center;
        margin: 2rem 0;
    ">
        <div style="font-size: 2.5rem; margin-bottom: 8px;">⚡</div>
        <div style="font-size: 1.3rem; font-weight: 600; color: #fff; margin-bottom: 6px;">Ready to Simulate</div>
        <div style="color: rgba(255,255,255,0.5); font-size: 0.95rem;">Configure your scenario in the sidebar, then click <b>▶ Run Simulation</b></div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

# ---------------------------------------------------------------------------
# RUN ENGINE
# ---------------------------------------------------------------------------
results: list[SimulationResult] = [run_simulation(scenario, cv) for cv in charger_variants]
st.session_state["results"] = results

# Shorthand refs used throughout
v = vehicle
p = pack

# ═══════════════════════════════════════════════════════════════════════════
# SECTION 1 — Derived Operational Parameters
# ═══════════════════════════════════════════════════════════════════════════
st.divider()
st.header("1 · Derived Operational Parameters")

# Pick first result for vehicle-level derived params (same across chargers)
d0 = results[0].derived

# --- Fleet inventory — styled cards ---
st.subheader("Fleet Inventory")
fi_cols = st.columns(5)
fi_cards = [
    ("🚗", "Vehicles", f"{d0.initial_fleet_size:,}", "#6c5ce7"),
    ("⚡", "Total Docks", f"{d0.total_docks:,}", "#00b894"),
    ("🔋", "Packs on Vehicles", f"{d0.packs_on_vehicles:,}", "#0984e3"),
    ("🔌", "Packs in Docks (Float)", f"{d0.packs_in_docks:,}", "#fdcb6e"),
    ("📦", "Total Packs", f"{d0.total_packs:,}", "#e17055"),
]
for col, (icon, label, value, accent) in zip(fi_cols, fi_cards):
    col.markdown(_card(icon, label, value, accent), unsafe_allow_html=True)

with st.expander("📐 Inventory formulas"):
    st.markdown(f"**Packs on vehicles** — `fleet × packs_per_vehicle` = {d0.initial_fleet_size:,} × {v.packs_per_vehicle} = **{d0.packs_on_vehicles:,}**")
    st.markdown(f"**Packs in docks (= float)** — `stations × docks_per_station` = {station.num_stations} × {station.docks_per_station} = **{d0.packs_in_docks:,}**")
    st.markdown(f"**Total packs** — {d0.packs_on_vehicles:,} + {d0.packs_in_docks:,} = **{d0.total_packs:,}**")

# --- Operational headline metrics ---
st.subheader("Operational Parameters")
m1, m2, m3, m4 = st.columns(4)
m1.metric("Energy per swap cycle / pack", f"{d0.energy_per_swap_cycle_per_pack_kwh:.3f} kWh",
          help="Energy consumed from one pack before driver swaps (behavioural, not hard limit)")
m2.metric("Swap visits / day / vehicle", f"{d0.swap_visits_per_vehicle_per_day:.2f}",
          help="Station visits per vehicle — all packs swapped per visit")
m3.metric("Pack lifetime", f"{d0.pack_lifetime_cycles:,} cycles")
m4.metric("Energy per visit / vehicle", f"{d0.energy_per_swap_cycle_per_vehicle_kwh:.2f} kWh",
          help="Total energy refilled per swap visit = packs × energy_per_pack")

# --- Per-charger derived (charge time & C-rate differ by charger) ---
if len(results) > 1:
    cols = st.columns(len(results))
    for col, res in zip(cols, results):
        dd = res.derived
        col.markdown(f"**{res.charger_variant_id}**")
        col.metric("Charge time", f"{dd.charge_time_minutes:.1f} min")
        col.metric("C-rate", f"{dd.effective_c_rate:.2f} C")
        col.metric("Cycles / day / dock", f"{dd.cycles_per_day_per_dock:.1f}")
else:
    dd = d0
    m1, m2, m3 = st.columns(3)
    m1.metric("Charge time", f"{dd.charge_time_minutes:.1f} min")
    m2.metric("C-rate", f"{dd.effective_c_rate:.2f} C")
    m3.metric("Cycles / day / dock", f"{dd.cycles_per_day_per_dock:.1f}")

# --- Formula detail ---
with st.expander("📐 Show formulas"):
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

# ═══════════════════════════════════════════════════════════════════════════
# SECTION 2 — Cost Per Cycle Waterfall
# ═══════════════════════════════════════════════════════════════════════════
st.divider()
st.header("2 · Cost Per Cycle Waterfall")

multi_charger = len(results) > 1

# ---------------------------------------------------------------------------
# Helper: render the full CPC detail block for one charger result
# ---------------------------------------------------------------------------
def _render_cpc_block(res: SimulationResult, show_label: bool = False):
    """Render CPC chart, table, swap economics, and TCO breakdowns for one result."""
    cv = next(c for c in charger_variants if c.name == res.charger_variant_id)
    cpc = res.cpc_waterfall
    tco = res.charger_tco
    dd = res.derived
    ptco = res.pack_tco

    if show_label:
        st.markdown(f"#### {res.charger_variant_id}")

    # --- Headline metrics ---
    cost_per_visit = cpc.total * v.packs_per_vehicle
    rev_per_visit = revenue_cfg.price_per_swap
    margin = rev_per_visit - cost_per_visit
    margin_color = "#00b894" if margin >= 0 else "#d63031"
    margin_sign = "+" if margin >= 0 else ""

    h_cols = st.columns(4)
    h_cards = [
        ("💰", "Cost per Cycle", f"₹{cpc.total:.2f}", "#6c5ce7"),
        ("📈", "Revenue / Visit", f"₹{rev_per_visit:.2f}", "#00b894"),
        ("📉", "Cost / Visit", f"₹{cost_per_visit:.2f}", "#0984e3"),
        ("🎯", "Margin / Visit", f"₹{margin:.2f}", margin_color),
    ]
    for col, (icon, label, value, accent) in zip(h_cols, h_cards):
        col.markdown(_card(icon, label, value, accent), unsafe_allow_html=True)
    st.write("")  # spacer

    components = [
        ("Battery", cpc.battery),
        ("Charger", cpc.charger),
        ("Electricity", cpc.electricity),
        ("Real estate", cpc.real_estate),
        ("Maintenance", cpc.maintenance),
        ("Insurance", cpc.insurance),
        ("Sabotage", cpc.sabotage),
        ("Logistics", cpc.logistics),
        ("Overhead", cpc.overhead),
    ]

    chart_data = {name: [val] for name, val in components}
    st.bar_chart(chart_data, horizontal=True, height=280, y_label="₹ / cycle", use_container_width=True)

    # --- CPC table ---
    cpc_table_rows = []
    for name, val in components:
        pct = (val / cpc.total * 100) if cpc.total > 0 else 0
        cpc_table_rows.append({"Component": name, "₹ / cycle": round(val, 4), "% of total": f"{pct:.1f}%"})
    cpc_table_rows.append({"Component": "TOTAL", "₹ / cycle": round(cpc.total, 4), "% of total": "100%"})
    st.dataframe(cpc_table_rows, use_container_width=True, hide_index=True)

    # --- Formula detail ---
    with st.expander("📐 CPC formulas"):
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

    # --- Charger TCO detail (FLEET-LEVEL) ---
    with st.expander("📋 Charger TCO breakdown (fleet-level)"):
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

        with st.expander("📐 TCO formulas (fleet-level MTBF)"):
            st.markdown(f"**Per-dock hours** — `hrs/day × 365 × years` = {station.operating_hours_per_day} × 365 × {sim_cfg.horizon_months/12:.0f} = **{per_dock_hrs:,.0f} hrs**")
            st.markdown(f"**Fleet operating hours** — `per_dock × total_docks` = {per_dock_hrs:,.0f} × {tco.total_docks} = **{tco.fleet_operating_hours:,.0f} hrs**")
            st.markdown(f"**Fleet failures** — `fleet_hours / MTBF` = {tco.fleet_operating_hours:,.0f} / {cv.mtbf_hours:,.0f} = **{tco.expected_failures_over_horizon:.2f}**")
            st.markdown(f"**Downtime** — `failures × MTTR` = {tco.expected_failures_over_horizon:.2f} × {cv.mttr_hours} = **{tco.total_downtime_hours:.1f} dock-hrs**")
            st.markdown(f"**Availability** — `MTBF / (MTBF + MTTR)` = {cv.mtbf_hours:,.0f} / ({cv.mtbf_hours:,.0f} + {cv.mttr_hours}) = **{tco.availability*100:.2f}%** ← steady-state statistic")
            st.markdown(f"**Fleet repairs** — `failures × repair_cost` = {tco.expected_failures_over_horizon:.2f} × {cv.repair_cost_per_event:,.0f} = **₹{tco.total_repair_cost:,.0f}**")
            st.markdown(f"**Fleet replacements** — `floor(failures / threshold)` = floor({tco.expected_failures_over_horizon:.2f} / {cv.replacement_threshold}) = **{tco.num_replacements}**")

    # --- Pack TCO detail (FLEET-LEVEL) ---
    with st.expander("📋 Pack failure TCO breakdown (fleet-level)"):
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

        with st.expander("📐 Pack TCO formulas (fleet-level MTBF)"):
            pack_hrs_per_yr = station.operating_hours_per_day * 365
            st.markdown(f"**Fleet operating hours** — `hrs/day × 365 × years × packs` = {station.operating_hours_per_day} × 365 × {sim_cfg.horizon_months/12:.0f} × {ptco.total_packs} = **{ptco.fleet_operating_hours:,.0f} hrs**")
            st.markdown(f"**Fleet failures** — `fleet_hours / MTBF` = {ptco.fleet_operating_hours:,.0f} / {p.mtbf_hours:,.0f} = **{ptco.expected_failures:.2f}**")
            st.markdown(f"**Downtime** — `failures × MTTR` = {ptco.expected_failures:.2f} × {p.mttr_hours} = **{ptco.total_downtime_hours:.1f} pack-hrs**")
            st.markdown(f"**Availability** — `MTBF / (MTBF + MTTR)` = {p.mtbf_hours:,.0f} / ({p.mtbf_hours:,.0f} + {p.mttr_hours}) = **{ptco.availability*100:.2f}%**")
            st.markdown(f"**Fleet repairs** — `failures × repair_cost` = {ptco.expected_failures:.2f} × {p.repair_cost_per_event:,.0f} = **₹{ptco.total_repair_cost:,.0f}**")
            st.markdown(f"**Fleet replacements** — `floor(failures / threshold)` = floor({ptco.expected_failures:.2f} / {p.replacement_threshold}) = **{ptco.num_replacements}**")


# --- Render: single charger → flat; multiple → tabs ---
if multi_charger:
    cpc_tabs = st.tabs([r.charger_variant_id for r in results])
    for cpc_tab, res in zip(cpc_tabs, results):
        with cpc_tab:
            _render_cpc_block(res)
else:
    _render_cpc_block(results[0])


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 3 — Monthly Cash Flow
# ═══════════════════════════════════════════════════════════════════════════
st.divider()
st.header("3 · Monthly Cash Flow")

# --- Cumulative CF line chart ---
if multi_charger:
    cf_chart_data = {}
    for res in results:
        cf_chart_data[res.charger_variant_id] = [s.cumulative_cash_flow for s in res.months]
    st.line_chart(cf_chart_data, y_label="Cumulative Cash Flow (₹)", x_label="Month", height=320, use_container_width=True)
else:
    cf_chart_data = {"Cumulative CF": [s.cumulative_cash_flow for s in results[0].months]}
    st.line_chart(cf_chart_data, y_label="Cumulative Cash Flow (₹)", x_label="Month", height=320, use_container_width=True)

# --- Break-even callout ---
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

# ---------------------------------------------------------------------------
# Helper: render cash flow detail for one result
# ---------------------------------------------------------------------------
def _render_cf_block(res: SimulationResult):
    cf_rows = []
    for s in res.months:
        cf_rows.append({
            "Month": s.month,
            "Fleet": s.fleet_size,
            "Visits": s.swap_visits,
            "Cycles": s.total_cycles,
            "Revenue (₹)": round(s.revenue),
            "OpEx (₹)": round(s.opex_total),
            "CapEx (₹)": round(s.capex_this_month),
            "Net CF (₹)": round(s.net_cash_flow),
            "Cum. CF (₹)": round(s.cumulative_cash_flow),
        })
    st.dataframe(
        cf_rows,
        use_container_width=True,
        hide_index=True,
        height=min(400, 35 * len(cf_rows) + 38),
    )

    sm = res.summary
    ncf_color = "#00b894" if sm.total_net_cash_flow >= 0 else "#d63031"
    sm_cols = st.columns(4)
    sm_cards = [
        ("📈", "Total Revenue", _fmt_inr(sm.total_revenue), "#00b894"),
        ("💸", "Total OpEx", _fmt_inr(sm.total_opex), "#e17055"),
        ("🏗️", "Total CapEx", _fmt_inr(sm.total_capex), "#0984e3"),
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


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 4 — Charger Comparison  (only when multiple variants)
# ═══════════════════════════════════════════════════════════════════════════
if multi_charger:
    st.divider()
    st.header("4 · Charger Comparison")

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
