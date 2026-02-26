"""Rich result rendering — displays SimulationResult as Streamlit components in chat."""

from __future__ import annotations

import uuid
from typing import Any

import streamlit as st
import plotly.graph_objects as go

from zng_simulator.models.results import SimulationResult


# ═══════════════════════════════════════════════════════════════════════════
# Shared styling (matches main dashboard)
# ═══════════════════════════════════════════════════════════════════════════

_COLORS = [
    "#6c5ce7", "#0984e3", "#00b894", "#fdcb6e",
    "#e17055", "#d63031", "#fd79a8", "#a29bfe", "#636e72",
]

_PLOTLY_LAYOUT = dict(
    height=300,
    margin=dict(l=20, r=20, t=40, b=20),
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter", size=11, color="rgba(255,255,255,0.7)"),
)


def _fmt_inr(val: float) -> str:
    if abs(val) >= 1e7:
        return f"₹{val / 1e7:,.2f} Cr"
    if abs(val) >= 1e5:
        return f"₹{val / 1e5:,.2f} L"
    return f"₹{val:,.0f}"


def _card(icon: str, label: str, value: str, accent: str = "#6c5ce7") -> str:
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


# ═══════════════════════════════════════════════════════════════════════════
# Metric cards
# ═══════════════════════════════════════════════════════════════════════════

def render_metric_cards(result: SimulationResult) -> None:
    s = result.summary
    w = result.cpc_waterfall

    cards = [
        ("💰", "Cost per Cycle", f"₹{w.total:.2f}", "#6c5ce7"),
        (
            "📈",
            "NPV",
            _fmt_inr(result.dcf.npv) if result.dcf else "N/A",
            "#00b894" if result.dcf and result.dcf.npv > 0 else "#d63031",
        ),
        (
            "📊",
            "IRR",
            f"{result.dcf.irr * 100:.1f}%" if result.dcf and result.dcf.irr else "N/A",
            "#0984e3",
        ),
        (
            "⏱️",
            "Break-even",
            f"Month {s.break_even_month}" if s.break_even_month else "Never",
            "#fdcb6e",
        ),
    ]
    if result.dscr:
        cards.append(("🏦", "Avg DSCR", f"{result.dscr.avg_dscr:.2f}", "#e17055"))

    cols = st.columns(len(cards))
    for col, (icon, label, value, accent) in zip(cols, cards):
        col.markdown(_card(icon, label, value, accent), unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════
# Cash flow chart
# ═══════════════════════════════════════════════════════════════════════════

def render_cash_flow_chart(result: SimulationResult) -> None:
    months = result.months
    if not months:
        return

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=[m.month for m in months],
        y=[m.cumulative_cash_flow for m in months],
        mode="lines",
        name="Cumulative CF",
        line=dict(color="#6c5ce7", width=2),
        fill="tozeroy",
        fillcolor="rgba(108,92,231,0.1)",
    ))
    fig.add_hline(y=0, line_dash="dot", line_color="rgba(255,255,255,0.3)")
    fig.update_layout(
        title="Cumulative Cash Flow",
        xaxis_title="Month",
        yaxis_title="₹",
        **_PLOTLY_LAYOUT,
    )
    st.plotly_chart(fig, use_container_width=True, key=f"chat_cf_{uuid.uuid4().hex[:8]}")


# ═══════════════════════════════════════════════════════════════════════════
# CPC waterfall
# ═══════════════════════════════════════════════════════════════════════════

def render_cpc_waterfall(result: SimulationResult) -> None:
    w = result.cpc_waterfall
    components = [
        ("Battery", w.battery),
        ("Charger", w.charger),
        ("Electricity", w.electricity),
        ("Real Estate", w.real_estate),
        ("Maintenance", w.maintenance),
        ("Insurance", w.insurance),
        ("Sabotage", w.sabotage),
        ("Logistics", w.logistics),
        ("Overhead", w.overhead),
    ]
    components.sort(key=lambda x: x[1], reverse=True)

    fig = go.Figure(go.Bar(
        y=[c[0] for c in components],
        x=[c[1] for c in components],
        orientation="h",
        marker_color=_COLORS[: len(components)],
    ))
    fig.update_layout(
        title=f"Cost per Cycle Breakdown (Total: ₹{w.total:.2f})",
        xaxis_title="₹/cycle",
        **_PLOTLY_LAYOUT,
    )
    st.plotly_chart(fig, use_container_width=True, key=f"chat_cpc_{uuid.uuid4().hex[:8]}")


# ═══════════════════════════════════════════════════════════════════════════
# Comparison table
# ═══════════════════════════════════════════════════════════════════════════

def render_comparison_table(results: list[SimulationResult]) -> None:
    import pandas as pd

    rows = []
    for r in results:
        rows.append({
            "Charger": r.summary.charger_variant_name,
            "CPC (₹)": round(r.cpc_waterfall.total, 2),
            "NPV (₹)": _fmt_inr(r.dcf.npv) if r.dcf else "N/A",
            "IRR": f"{r.dcf.irr * 100:.1f}%" if r.dcf and r.dcf.irr else "N/A",
            "Break-even": f"Mo. {r.summary.break_even_month}" if r.summary.break_even_month else "Never",
            "Net CF (₹)": _fmt_inr(r.summary.total_net_cash_flow),
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════════════════════════════════════
# Tornado chart (sensitivity)
# ═══════════════════════════════════════════════════════════════════════════

def render_tornado_chart(data: dict) -> None:
    bars = data.get("tornado_bars", [])
    if not bars:
        return

    base_npv = data.get("base_npv", 0)
    names = [b["param_name"] for b in bars]
    low_deltas = [b["npv_at_low"] - base_npv for b in bars]
    high_deltas = [b["npv_at_high"] - base_npv for b in bars]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=names,
        x=low_deltas,
        orientation="h",
        name="Low",
        marker_color="#e17055",
    ))
    fig.add_trace(go.Bar(
        y=names,
        x=high_deltas,
        orientation="h",
        name="High",
        marker_color="#00b894",
    ))
    fig.update_layout(
        title=f"NPV Sensitivity (Base: {_fmt_inr(base_npv)})",
        xaxis_title="ΔNPV (₹)",
        barmode="overlay",
        **_PLOTLY_LAYOUT,
    )
    st.plotly_chart(fig, use_container_width=True, key=f"chat_tornado_{uuid.uuid4().hex[:8]}")


# ═══════════════════════════════════════════════════════════════════════════
# Monte Carlo summary
# ═══════════════════════════════════════════════════════════════════════════

def render_monte_carlo_summary(result: SimulationResult) -> None:
    mc = result.monte_carlo
    if not mc:
        return

    cards = [
        ("📉", "NCF P10", _fmt_inr(mc.ncf_p10), "#e17055"),
        ("📊", "NCF P50", _fmt_inr(mc.ncf_p50), "#fdcb6e"),
        ("📈", "NCF P90", _fmt_inr(mc.ncf_p90), "#00b894"),
    ]
    cols = st.columns(len(cards))
    for col, (icon, label, value, accent) in zip(cols, cards):
        col.markdown(_card(icon, label, value, accent), unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════
# Top-level dispatcher
# ═══════════════════════════════════════════════════════════════════════════

def render_chat_result(
    tool_name: str,
    data: dict,
    sim_result: SimulationResult | list[SimulationResult] | None,
) -> None:
    """Render rich results based on which tool was called."""

    if tool_name == "run_simulation" and isinstance(sim_result, SimulationResult):
        render_metric_cards(sim_result)
        render_cash_flow_chart(sim_result)
        render_cpc_waterfall(sim_result)
        if sim_result.monte_carlo:
            render_monte_carlo_summary(sim_result)

    elif tool_name == "compare_chargers" and isinstance(sim_result, list):
        render_comparison_table(sim_result)
        # Also show the best charger's cash flow
        if sim_result:
            best = min(sim_result, key=lambda r: r.cpc_waterfall.total)
            st.caption(f"Cash flow for best variant: {best.summary.charger_variant_name}")
            render_cash_flow_chart(best)

    elif tool_name == "run_sensitivity":
        render_tornado_chart(data)

    elif tool_name == "optimize_fleet_size" and isinstance(sim_result, SimulationResult):
        render_metric_cards(sim_result)
        render_cash_flow_chart(sim_result)
