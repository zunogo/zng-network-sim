"""Investor-grade unit economics PDF report.

All figures derive from simulator outputs. No hardcoded benchmarks,
no fabricated narrative numbers, no filler when data is absent.
"""

from __future__ import annotations

import io
from datetime import date
from pathlib import Path
from typing import Any

import plotly.graph_objects as go
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from zng_simulator.config.scenario import Scenario
from zng_simulator.dashboard._format import fmt_inr
from zng_simulator.finance.bundle import FinanceBundle
from zng_simulator.models.results import MonteCarloSummary, SimulationResult


# ---------------------------------------------------------------------------
# Bundled Unicode fonts — DejaVuSans has the ₹ glyph (U+20B9) which the
# reportlab built-ins do not. Fonts ship inside the package.
# ---------------------------------------------------------------------------

_FONTS_DIR = Path(__file__).parent / "fonts"
FONT_BODY = "DejaVu"
FONT_BOLD = "DejaVu-Bold"
FONT_ITALIC = "DejaVu-Oblique"


def _register_fonts_once() -> None:
    if FONT_BODY in pdfmetrics.getRegisteredFontNames():
        return
    pdfmetrics.registerFont(TTFont(FONT_BODY, str(_FONTS_DIR / "DejaVuSans.ttf")))
    pdfmetrics.registerFont(TTFont(FONT_BOLD, str(_FONTS_DIR / "DejaVuSans-Bold.ttf")))
    pdfmetrics.registerFont(TTFont(FONT_ITALIC, str(_FONTS_DIR / "DejaVuSans-Oblique.ttf")))


ACCENT_PURPLE = colors.HexColor("#6c5ce7")
ACCENT_GREEN = colors.HexColor("#00b894")
ACCENT_BLUE = colors.HexColor("#0984e3")
ACCENT_YELLOW = colors.HexColor("#fdcb6e")
ACCENT_ORANGE = colors.HexColor("#e17055")
ACCENT_RED = colors.HexColor("#d63031")
BRAND_YELLOW = colors.HexColor("#facc15")

INK = colors.HexColor("#1a1a1a")
MUTED = colors.HexColor("#6b6b6b")
SUBTLE = colors.HexColor("#9a9a9a")
LIGHT_GREY = colors.HexColor("#e8e8e8")
SECTION_BG = colors.HexColor("#fafafa")

# A4 page width 210mm minus 18mm L/R margins → 174mm content width
PAGE_W = 174 * mm
KPI_GAP = 4 * mm
KPI_W = (PAGE_W - 3 * KPI_GAP) / 4
TABLE_LABEL_W = PAGE_W * 0.62
TABLE_VALUE_W = PAGE_W * 0.38


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "brand": ParagraphStyle(
            "brand", parent=base["Normal"],
            fontName=FONT_BOLD, fontSize=20, leading=24,
            textColor=BRAND_YELLOW, spaceAfter=2,
        ),
        "title": ParagraphStyle(
            "title", parent=base["Normal"],
            fontName=FONT_BOLD, fontSize=14, leading=18,
            textColor=INK, spaceAfter=2,
        ),
        "subtitle": ParagraphStyle(
            "subtitle", parent=base["Normal"],
            fontName=FONT_BODY, fontSize=9, leading=12,
            textColor=MUTED, spaceAfter=10,
        ),
        "section": ParagraphStyle(
            "section", parent=base["Normal"],
            fontName=FONT_BOLD, fontSize=12, leading=15,
            textColor=INK, spaceBefore=10, spaceAfter=2,
        ),
        "caption": ParagraphStyle(
            "caption", parent=base["Normal"],
            fontName=FONT_BODY, fontSize=8.5, leading=11,
            textColor=MUTED, spaceAfter=8,
        ),
        "subsection": ParagraphStyle(
            "subsection", parent=base["Normal"],
            fontName=FONT_BOLD, fontSize=9.5, leading=12,
            textColor=ACCENT_PURPLE, spaceBefore=8, spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "body", parent=base["Normal"],
            fontName=FONT_BODY, fontSize=9.5, leading=13,
            textColor=INK, spaceAfter=6,
        ),
        "body_muted": ParagraphStyle(
            "body_muted", parent=base["Normal"],
            fontName=FONT_BODY, fontSize=9.5, leading=13,
            textColor=MUTED,
        ),
        "kpi_label": ParagraphStyle(
            "kpi_label", parent=base["Normal"],
            fontName=FONT_BODY, fontSize=7.5, leading=9,
            textColor=MUTED, alignment=1,
        ),
        "kpi_value": ParagraphStyle(
            "kpi_value", parent=base["Normal"],
            fontName=FONT_BOLD, fontSize=13, leading=16,
            textColor=INK, alignment=1,
        ),
        "chip_value": ParagraphStyle(
            "chip_value", parent=base["Normal"],
            fontName=FONT_BOLD, fontSize=11, leading=14,
            textColor=INK, alignment=1,
        ),
        "chip_label": ParagraphStyle(
            "chip_label", parent=base["Normal"],
            fontName=FONT_BODY, fontSize=7.5, leading=9.5,
            textColor=MUTED, alignment=1,
        ),
        "footer_body": ParagraphStyle(
            "footer_body", parent=base["Normal"],
            fontName=FONT_BODY, fontSize=8, leading=11,
            textColor=MUTED,
        ),
    }


# ---------------------------------------------------------------------------
# Data collection (testable: every value is a projection of simulator output)
# ---------------------------------------------------------------------------

def _payback_label(month: int | None) -> str:
    return f"Month {month}" if month is not None else "Never"


def _irr_label(irr: float | None) -> str:
    return f"{irr * 100:.1f}%" if irr is not None else "N/A"


def _collect_report_data(
    scenario: Scenario,
    result: SimulationResult,
    bundle: FinanceBundle,
    mc_summary: MonteCarloSummary | None,
    scenario_name: str | None,
    today: date | None = None,
) -> dict[str, Any]:
    """Pure data collection — every value traces to a simulator/scenario field.

    Tests assert this dict's values against the source objects directly.
    """
    summary = result.summary
    derived = result.derived
    waterfall = result.cpc_waterfall
    revenue_cfg = scenario.revenue
    sim_cfg = scenario.simulation
    finance_cfg = scenario.finance
    opex_cfg = scenario.opex
    pack = scenario.pack
    station = scenario.station
    vehicle = scenario.vehicle
    demand_cfg = scenario.demand
    chaos_cfg = scenario.chaos
    primary_cv = next(
        (c for c in scenario.charger_variants if c.name == result.charger_variant_id),
        scenario.charger_variants[0],
    )
    dcf = bundle.dcf

    # Pack lifetime in years: derived from cycle life and observed cycle rate per pack
    cycles_per_pack_per_month = (
        derived.total_network_cycles_per_month / derived.total_packs
        if derived.total_packs > 0 else 0.0
    )
    pack_lifetime_years = (
        pack.cycle_life_to_retirement / (cycles_per_pack_per_month * 12)
        if cycles_per_pack_per_month > 0 else None
    )

    data: dict[str, Any] = {
        "scenario_name": scenario_name,
        "generated_on": (today or date.today()).isoformat(),
        "horizon_months": sim_cfg.horizon_months,
        "engine": sim_cfg.engine,

        # Cover row
        "num_stations": station.num_stations,
        "total_docks": derived.total_docks,
        "fleet_size": revenue_cfg.initial_fleet_size,
        "total_packs": derived.total_packs,
        "charger_variant_name": primary_cv.name,

        # Scenario configuration — what was actually modeled
        "config": {
            "network": (
                f"{station.num_stations} stations · {station.docks_per_station} docks/station · "
                f"{station.operating_hours_per_day:.0f} hrs/day"
            ),
            "fleet": (
                f"{revenue_cfg.initial_fleet_size:,} vehicles ({vehicle.name}) · "
                f"{vehicle.packs_per_vehicle} packs/veh · "
                f"{vehicle.avg_daily_km:.0f} km/day · "
                f"{vehicle.energy_consumption_wh_per_km:.0f} Wh/km"
            ),
            "pack": (
                f"{pack.nominal_capacity_kwh} kWh {pack.chemistry} · "
                f"{pack.cycle_life_to_retirement:,}-cycle life · "
                f"{fmt_inr(pack.unit_cost)} per pack"
            ),
            "charger": (
                f"{primary_cv.name} · {primary_cv.rated_power_w/1000:.1f} kW · "
                f"{primary_cv.charging_efficiency_pct * 100:.0f}% efficiency · "
                f"{fmt_inr(primary_cv.purchase_cost_per_slot)}/slot"
            ),
            "pricing": f"₹{revenue_cfg.price_per_swap:.0f} per swap",
            "finance": (
                f"WACC {sim_cfg.discount_rate_annual*100:.1f}% · "
                f"Debt {finance_cfg.debt_pct_of_capex*100:.0f}% @ "
                f"{finance_cfg.interest_rate_annual*100:.1f}% · "
                f"Tax {finance_cfg.tax_rate*100:.0f}%"
            ),
            "demand": (
                f"{demand_cfg.distribution} · σ={demand_cfg.volatility:.2f} · "
                f"weekend ×{demand_cfg.weekend_factor:.1f}"
            ),
            "engine_horizon": (
                f"{sim_cfg.engine} engine · {sim_cfg.horizon_months}-month horizon"
                + (f" · {sim_cfg.monte_carlo_runs:,} MC runs" if sim_cfg.engine == "stochastic" and sim_cfg.monte_carlo_runs > 1 else "")
            ),
        },

        # Operating insights — three derived punchlines, all from simulator outputs
        "operating_insights": {
            "swaps_per_vehicle_per_day": derived.swap_visits_per_vehicle_per_day,
            "cycles_per_dock_per_day": derived.cycles_per_day_per_dock,
            "pack_lifetime_years": pack_lifetime_years,
        },

        # Risk & reliability knobs — assumptions that stress the model
        "risk_knobs": {
            "range_anxiety_buffer_pct": vehicle.range_anxiety_buffer_pct,
            "cycle_degradation_rate_pct": pack.cycle_degradation_rate_pct,
            "calendar_aging_rate_pct_per_month": pack.calendar_aging_rate_pct_per_month,
            "sabotage_pct_per_month": chaos_cfg.sabotage_pct_per_month,
            "charger_failure_distribution": primary_cv.failure_distribution,
            "charger_weibull_shape": primary_cv.weibull_shape,
        },

        # CapEx / OpEx breakdown — values mirror what the cards render
        "costs": {
            "capex": {
                # lumped per-station setup: cabinet + site prep + grid connection + security deposit
                "per_station_setup": (
                    station.cabinet_cost + station.site_prep_cost
                    + station.grid_connection_cost + station.security_deposit
                ),
                "software_one_time": station.software_cost,
                "charger_per_slot": primary_cv.purchase_cost_per_slot,
                "pack_unit_cost": pack.unit_cost,
                "total_initial_capex": bundle.total_initial_capex,
            },
            "opex": {
                "rent_per_station_monthly": opex_cfg.rent_per_month_per_station,
                # lumped "other" per-station fixed OpEx (5 smaller items)
                "other_station_per_month": (
                    opex_cfg.preventive_maintenance_per_month_per_station
                    + opex_cfg.corrective_maintenance_per_month_per_station
                    + opex_cfg.insurance_per_month_per_station
                    + opex_cfg.logistics_per_month_per_station
                    + opex_cfg.auxiliary_power_per_month
                ),
                "overhead_monthly": opex_cfg.overhead_per_month,
                "electricity_tariff_per_kwh": opex_cfg.electricity_tariff_per_kwh,
                "labor_per_swap": opex_cfg.pack_handling_labor_per_swap,
                "fixed_monthly_burn": (
                    (opex_cfg.rent_per_month_per_station
                     + opex_cfg.preventive_maintenance_per_month_per_station
                     + opex_cfg.corrective_maintenance_per_month_per_station
                     + opex_cfg.insurance_per_month_per_station
                     + opex_cfg.logistics_per_month_per_station
                     + opex_cfg.auxiliary_power_per_month) * station.num_stations
                    + opex_cfg.overhead_per_month
                ),
            },
        },

        # Headline KPIs
        "avg_cost_per_cycle": summary.avg_cost_per_cycle,
        "price_per_swap": revenue_cfg.price_per_swap,
        "npv": dcf.npv,
        "irr": dcf.irr,
        "discounted_payback_month": dcf.discounted_payback_month,
        "terminal_value": dcf.terminal_value,

        # Horizon totals
        "total_revenue": summary.total_revenue,
        "total_opex": summary.total_opex,
        "total_capex": summary.total_capex,
        "total_net_cash_flow": summary.total_net_cash_flow,
        "break_even_month": summary.break_even_month,

        # Cost-per-cycle waterfall (₹/cycle)
        "cpc": {
            "battery": waterfall.battery,
            "charger": waterfall.charger,
            "electricity": waterfall.electricity,
            "real_estate": waterfall.real_estate,
            "maintenance": waterfall.maintenance,
            "insurance": waterfall.insurance,
            "sabotage": waterfall.sabotage,
            "logistics": waterfall.logistics,
            "overhead": waterfall.overhead,
            "total": waterfall.total,
        },

        # Cumulative PV trajectory
        "cumulative_pv": [r.cumulative_pv for r in dcf.monthly_dcf],

        # Reliability — None-valued fields are excluded later when rendering
        "reliability": {
            "charger_availability": result.charger_tco.availability,
            "pack_availability": result.pack_tco.availability,
            "expected_charger_failures": result.charger_tco.expected_failures_over_horizon,
            "expected_pack_failures": result.pack_tco.expected_failures,
            "total_charger_failures": summary.total_charger_failures,
            "total_packs_retired": summary.total_packs_retired,
            "mean_soh_at_end": summary.mean_soh_at_end,
            "total_failure_to_serve": summary.total_failure_to_serve,
        },

        # Per-station economics
        "per_station": {
            "cycles_per_dock_per_day": derived.cycles_per_day_per_dock,
            "swap_visits_per_vehicle_per_day": derived.swap_visits_per_vehicle_per_day,
            "cycles_per_month_per_station": derived.cycles_per_month_per_station,
            "revenue_per_cycle": revenue_cfg.price_per_swap,
            "cost_per_cycle": summary.avg_cost_per_cycle,
        },

        # Assumptions
        "assumptions": {
            "discount_rate_annual": sim_cfg.discount_rate_annual,
            "debt_pct_of_capex": finance_cfg.debt_pct_of_capex,
            "interest_rate_annual": finance_cfg.interest_rate_annual,
            "tax_rate": finance_cfg.tax_rate,
            "electricity_tariff_per_kwh": opex_cfg.electricity_tariff_per_kwh,
            "pack_unit_cost": pack.unit_cost,
            "charger_purchase_cost_per_slot": primary_cv.purchase_cost_per_slot,
            "pack_mtbf_hours": pack.mtbf_hours,
            "pack_mttr_hours": pack.mttr_hours,
            "charger_mtbf_hours": primary_cv.mtbf_hours,
            "charger_mttr_hours": primary_cv.mttr_hours,
        },

        "monte_carlo": (
            {
                "num_runs": mc_summary.num_runs,
                "ncf_p10": mc_summary.ncf_p10,
                "ncf_p50": mc_summary.ncf_p50,
                "ncf_p90": mc_summary.ncf_p90,
                "cpc_p10": mc_summary.cpc_p10,
                "cpc_p50": mc_summary.cpc_p50,
                "cpc_p90": mc_summary.cpc_p90,
                "break_even_p10": mc_summary.break_even_p10,
                "break_even_p50": mc_summary.break_even_p50,
                "break_even_p90": mc_summary.break_even_p90,
                "avg_packs_retired": mc_summary.avg_packs_retired,
                "avg_charger_failures": mc_summary.avg_charger_failures,
                "avg_failure_to_serve": mc_summary.avg_failure_to_serve,
            }
            if mc_summary is not None
            else None
        ),
    }
    return data


# ---------------------------------------------------------------------------
# Charts → PNG bytes (via plotly + kaleido)
# ---------------------------------------------------------------------------

def _waterfall_png(cpc: dict[str, float]) -> bytes:
    components = [
        ("Battery", cpc["battery"]),
        ("Charger", cpc["charger"]),
        ("Electricity", cpc["electricity"]),
        ("Real Estate", cpc["real_estate"]),
        ("Maintenance", cpc["maintenance"]),
        ("Insurance", cpc["insurance"]),
        ("Sabotage", cpc["sabotage"]),
        ("Logistics", cpc["logistics"]),
        ("Overhead", cpc["overhead"]),
    ]
    fig = go.Figure(go.Waterfall(
        orientation="v",
        measure=["relative"] * len(components) + ["total"],
        x=[name for name, _ in components] + ["Total"],
        y=[v for _, v in components] + [cpc["total"]],
        text=[f"₹{v:.2f}" for _, v in components] + [f"₹{cpc['total']:.2f}"],
        textposition="outside",
        connector={"line": {"color": "#bbbbbb"}},
        increasing={"marker": {"color": "#fdcb6e"}},
        totals={"marker": {"color": "#6c5ce7"}},
    ))
    fig.update_layout(
        title=dict(text="Cost per Cycle (₹) — Component Waterfall", x=0.0,
                   font=dict(family="Helvetica", size=13, color="#1a1a1a")),
        font=dict(family="Helvetica", size=10, color="#1a1a1a"),
        margin=dict(l=44, r=10, t=40, b=30),
        plot_bgcolor="white",
        paper_bgcolor="white",
        yaxis=dict(title=dict(text="₹ / cycle", standoff=4),
                   gridcolor="#eaeaea"),
        showlegend=False,
        height=360,
        width=900,
    )
    return fig.to_image(format="png", engine="kaleido", scale=2)


def _cumulative_pv_png(cumulative_pv: list[float], payback_month: int | None) -> bytes:
    months = list(range(1, len(cumulative_pv) + 1))
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=months, y=cumulative_pv, mode="lines",
        line=dict(color="#0984e3", width=2.5),
        fill="tozeroy", fillcolor="rgba(9,132,227,0.10)",
        name="Cumulative PV",
    ))
    fig.add_hline(y=0, line=dict(color="#888888", width=1, dash="dot"))
    if payback_month is not None and 1 <= payback_month <= len(cumulative_pv):
        fig.add_vline(x=payback_month, line=dict(color="#00b894", width=1.5, dash="dash"))
        fig.add_annotation(
            x=payback_month, y=cumulative_pv[payback_month - 1],
            text=f"Payback · Month {payback_month}",
            showarrow=True, arrowhead=2, ax=40, ay=-30,
            font=dict(family="Helvetica", size=10, color="#00b894"),
        )
    fig.update_layout(
        title=dict(text="Cumulative Present Value (₹)", x=0.0,
                   font=dict(family="Helvetica", size=13, color="#1a1a1a")),
        font=dict(family="Helvetica", size=10, color="#1a1a1a"),
        margin=dict(l=50, r=10, t=40, b=30),
        plot_bgcolor="white", paper_bgcolor="white",
        xaxis=dict(title=dict(text="Month", standoff=4), gridcolor="#eaeaea"),
        yaxis=dict(title=dict(text="₹ (PV)", standoff=4), gridcolor="#eaeaea"),
        showlegend=False,
        height=300,
        width=900,
    )
    return fig.to_image(format="png", engine="kaleido", scale=2)


# ---------------------------------------------------------------------------
# Section builders → list of platypus flowables
# ---------------------------------------------------------------------------

def _insight_chip(value: str, label: str, styles: dict[str, ParagraphStyle], chip_w: float) -> Table:
    """Compact derived-metric chip — lighter weight than the headline KPI card."""
    chip = Table(
        [[Paragraph(value, styles["chip_value"])],
         [Paragraph(label, styles["chip_label"])]],
        colWidths=[chip_w],
        rowHeights=[0.65 * cm, 0.45 * cm],
    )
    chip.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), SECTION_BG),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, 0), 5),
        ("TOPPADDING", (0, 1), (-1, 1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 0),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 5),
    ]))
    return chip


def _kpi_card(label: str, value: str, accent: colors.Color, styles: dict[str, ParagraphStyle]) -> Table:
    inner = Table(
        [[Paragraph(value, styles["kpi_value"])],
         [Paragraph(label.upper(), styles["kpi_label"])]],
        colWidths=[KPI_W],
        rowHeights=[1.0 * cm, 0.7 * cm],
    )
    inner.setStyle(TableStyle([
        ("LINEABOVE", (0, 0), (-1, 0), 2.5, accent),
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ("BOX", (0, 0), (-1, -1), 0.5, LIGHT_GREY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return inner


def _kv_table(
    rows: list[tuple[str, str]],
    col1_width: float = TABLE_LABEL_W,
    col2_width: float = TABLE_VALUE_W,
) -> Table:
    t = Table(rows, colWidths=[col1_width, col2_width], hAlign="LEFT")
    style = [
        ("FONTNAME", (0, 0), (0, -1), FONT_BODY),
        ("FONTNAME", (1, 0), (1, -1), FONT_BOLD),
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("TEXTCOLOR", (0, 0), (0, -1), MUTED),
        ("TEXTCOLOR", (1, 0), (1, -1), INK),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("LINEBELOW", (0, 0), (-1, -2), 0.25, LIGHT_GREY),
    ]
    t.setStyle(TableStyle(style))
    return t


def _config_table(rows: list[tuple[str, str]], styles: dict[str, ParagraphStyle]) -> Table:
    """Left-aligned label/value table for descriptive configuration strings."""
    body_rows = [
        [Paragraph(label, styles["body_muted"]), Paragraph(value, styles["body"])]
        for label, value in rows
    ]
    t = Table(body_rows, colWidths=[PAGE_W * 0.18, PAGE_W * 0.82], hAlign="LEFT")
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 0), (-1, -2), 0.25, LIGHT_GREY),
    ]))
    return t


def _kv_table_with_total(
    rows: list[tuple[str, str]],
    total: tuple[str, str],
    col1_width: float,
    col2_width: float,
) -> Table:
    """kv_table variant with a visually emphasised bold total row at the bottom."""
    all_rows = list(rows) + [total]
    t = Table(all_rows, colWidths=[col1_width, col2_width], hAlign="LEFT")
    last = len(all_rows) - 1
    style = [
        ("FONTNAME", (0, 0), (0, -1), FONT_BODY),
        ("FONTNAME", (1, 0), (1, -1), FONT_BOLD),
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("TEXTCOLOR", (0, 0), (0, last - 1), MUTED),
        ("TEXTCOLOR", (1, 0), (1, last - 1), INK),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("LINEBELOW", (0, 0), (-1, last - 2), 0.25, LIGHT_GREY),
        # Emphasise the total row: thicker rule above + bold both columns + ink color
        ("LINEABOVE", (0, last), (-1, last), 1.0, INK),
        ("FONTNAME", (0, last), (0, last), FONT_BOLD),
        ("FONTSIZE", (0, last), (-1, last), 10),
        ("TEXTCOLOR", (0, last), (-1, last), INK),
        ("TOPPADDING", (0, last), (-1, last), 8),
        ("BOTTOMPADDING", (0, last), (-1, last), 4),
    ]
    t.setStyle(TableStyle(style))
    return t


def _assumption_card(
    title: str,
    accent: colors.Color,
    rows: list[tuple[str, str]],
    subtitle: str | None = None,
    total: tuple[str, str] | None = None,
) -> Table:
    """Boxed sub-section with a colored top accent.

    If `total` is provided, the rows are rendered with a visually emphasised
    bold total row at the bottom (used for CapEx and OpEx cards).
    """
    inner_w = PAGE_W - 20  # account for 10pt L/R card padding
    if total is not None:
        body = _kv_table_with_total(
            rows, total,
            col1_width=inner_w * 0.62,
            col2_width=inner_w * 0.38,
        )
    else:
        body = _kv_table(
            rows,
            col1_width=inner_w * 0.62,
            col2_width=inner_w * 0.38,
        )
    base = getSampleStyleSheet()["Normal"]
    title_html = f"<font name='{FONT_BOLD}' color='#1a1a1a' size=10>{title}</font>"
    if subtitle:
        title_html += f"<br/><font name='{FONT_BODY}' color='#6b6b6b' size=8.5>{subtitle}</font>"
    card = Table(
        [[Paragraph(title_html, base)],
         [body]],
        colWidths=[PAGE_W],
        hAlign="LEFT",
    )
    card.setStyle(TableStyle([
        ("LINEABOVE", (0, 0), (-1, 0), 2.5, accent),
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ("BOX", (0, 0), (-1, -1), 0.5, LIGHT_GREY),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (0, 0), 8),
        ("BOTTOMPADDING", (0, 0), (0, 0), 6),
        ("TOPPADDING", (0, 1), (0, 1), 0),
        ("BOTTOMPADDING", (0, 1), (0, 1), 8),
    ]))
    return card


def _cover_section(data: dict[str, Any], styles: dict[str, ParagraphStyle]) -> list:
    flow: list = []

    # Brand band — full page width
    brand_band = Table(
        [[Paragraph("Zunogo", styles["brand"]),
          Paragraph(
              f"<font color='#6b6b6b'>Generated {data['generated_on']}</font>",
              styles["body"],
          )]],
        colWidths=[PAGE_W * 0.55, PAGE_W * 0.45],
        hAlign="LEFT",
    )
    brand_band.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ("LINEBELOW", (0, 0), (-1, -1), 1.5, BRAND_YELLOW),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    flow.append(brand_band)
    flow.append(Spacer(1, 8))
    flow.append(Paragraph("Unit Economics Report", styles["title"]))
    flow.append(Spacer(1, 6))

    # Executive paragraph (templated, all values from simulator)
    exec_text = (
        f"Over a {data['horizon_months']}-month projection, a "
        f"{data['num_stations']}-station network with {data['total_docks']} docks "
        f"serves {data['fleet_size']:,} vehicles using the "
        f"<b>{data['charger_variant_name']}</b> charger. The model produces an "
        f"average cost-per-cycle of <b>{fmt_inr(data['avg_cost_per_cycle'])}</b> "
        f"against a price-per-swap of <b>{fmt_inr(data['price_per_swap'])}</b>, "
        f"an NPV of <b>{fmt_inr(data['npv'])}</b>, an IRR of "
        f"<b>{_irr_label(data['irr'])}</b>, and discounted payback at "
        f"<b>{_payback_label(data['discounted_payback_month'])}</b>."
    )
    flow.append(Paragraph(exec_text, styles["body"]))
    flow.append(Spacer(1, 6))

    # 4 KPI cards — evenly spaced, full page width
    npv_accent = ACCENT_GREEN if data["npv"] >= 0 else ACCENT_RED
    cards = [
        _kpi_card("Avg Cost / Cycle", fmt_inr(data["avg_cost_per_cycle"]), ACCENT_YELLOW, styles),
        _kpi_card("Net Present Value", fmt_inr(data["npv"]), npv_accent, styles),
        _kpi_card("IRR (Annual)", _irr_label(data["irr"]), ACCENT_PURPLE, styles),
        _kpi_card("Discounted Payback", _payback_label(data["discounted_payback_month"]), ACCENT_BLUE, styles),
    ]
    cards_row = Table(
        [cards],
        colWidths=[KPI_W + KPI_GAP] * 4,
        hAlign="LEFT",
    )
    cards_row.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    flow.append(cards_row)
    flow.append(Spacer(1, 14))

    # Scenario Configuration — what was modeled (input context)
    cfg = data["config"]
    flow.append(Paragraph("Scenario Configuration", styles["section"]))
    flow.append(_config_table([
        ("Network", cfg["network"]),
        ("Fleet", cfg["fleet"]),
        ("Pack", cfg["pack"]),
        ("Charger", cfg["charger"]),
        ("Pricing", cfg["pricing"]),
        ("Finance", cfg["finance"]),
        ("Demand", cfg["demand"]),
        ("Simulation", cfg["engine_horizon"]),
    ], styles))

    # Operating insight chips — three derived numbers translating inputs into reality
    insights = data["operating_insights"]
    pack_life_str = (
        f"~{insights['pack_lifetime_years']:.1f} yrs"
        if insights["pack_lifetime_years"] is not None
        else "—"
    )
    chip_gap = 4 * mm
    chip_w = (PAGE_W - 2 * chip_gap) / 3
    chips = [
        _insight_chip(
            f"{insights['swaps_per_vehicle_per_day']:.2f}",
            "swaps / vehicle / day",
            styles, chip_w,
        ),
        _insight_chip(
            f"{insights['cycles_per_dock_per_day']:.1f}",
            "cycles / dock / day",
            styles, chip_w,
        ),
        _insight_chip(
            pack_life_str,
            "pack life at observed cadence",
            styles, chip_w,
        ),
    ]
    chips_row = Table(
        [chips],
        colWidths=[chip_w + chip_gap, chip_w + chip_gap, chip_w],
        hAlign="LEFT",
    )
    chips_row.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    flow.append(Spacer(1, 8))
    flow.append(chips_row)
    flow.append(Spacer(1, 14))

    # Horizon totals — outputs (kept on page 1 alongside the headlines)
    flow.append(Paragraph(f"{data['horizon_months']}-Month Totals", styles["section"]))
    flow.append(_kv_table([
        ("Total revenue", fmt_inr(data["total_revenue"])),
        ("Total OpEx", fmt_inr(data["total_opex"])),
        ("Total CapEx", fmt_inr(data["total_capex"])),
        ("Total net cash flow", fmt_inr(data["total_net_cash_flow"])),
        ("Break-even month", _payback_label(data["break_even_month"])),
    ]))

    return flow


def _unit_economics_section(data: dict[str, Any], styles: dict[str, ParagraphStyle]) -> list:
    flow: list = [PageBreak(), Paragraph("Unit Economics", styles["title"]), Spacer(1, 8)]

    # Waterfall chart — chart's internal title labels it
    waterfall_bytes = _waterfall_png(data["cpc"])
    waterfall_img = Image(io.BytesIO(waterfall_bytes), width=PAGE_W, height=PAGE_W * (360 / 900))
    waterfall_img.hAlign = "LEFT"
    flow.append(waterfall_img)
    flow.append(Spacer(1, 8))

    # Cumulative PV chart (only if data exists) — chart's internal title labels it
    if data["cumulative_pv"]:
        pv_bytes = _cumulative_pv_png(data["cumulative_pv"], data["discounted_payback_month"])
        pv_img = Image(io.BytesIO(pv_bytes), width=PAGE_W, height=PAGE_W * (300 / 900))
        pv_img.hAlign = "LEFT"
        flow.append(pv_img)
        flow.append(Spacer(1, 10))

    # Operations Snapshot — single consolidated full-width table.
    # Wrapped in KeepTogether so it never splits mid-table across pages.
    rel = data["reliability"]
    ps = data["per_station"]
    flow.append(KeepTogether([
        Paragraph("Operations Snapshot", styles["section"]),
        _kv_table([
            ("Cycles per dock per day", f"{ps['cycles_per_dock_per_day']:.2f}"),
            ("Cycles per month per station", f"{ps['cycles_per_month_per_station']:,.0f}"),
            ("Revenue per cycle", fmt_inr(ps["revenue_per_cycle"])),
            ("Cost per cycle (avg)", fmt_inr(ps["cost_per_cycle"])),
        ]),
    ]))

    return flow


def _input_parameters_section(data: dict[str, Any], styles: dict[str, ParagraphStyle]) -> list:
    a = data["assumptions"]
    capex = data["costs"]["capex"]
    opex = data["costs"]["opex"]

    # ── Single Inputs page — Cost & Operating ───────────────────────────────
    flow: list = [PageBreak(),
                  Paragraph("Cost & Operating Inputs", styles["title"]),
                  Spacer(1, 10)]

    flow.append(_assumption_card(
        "Capital Expenditure (CapEx)",
        ACCENT_YELLOW,
        [
            ("Per-station setup", f"{fmt_inr(capex['per_station_setup'])} / station"),
            ("Software platform", f"{fmt_inr(capex['software_one_time'])} (one-time)"),
            ("Charger slot", f"{fmt_inr(capex['charger_per_slot'])} / dock"),
            ("Battery pack", f"{fmt_inr(capex['pack_unit_cost'])} / pack"),
        ],
        subtitle="Upfront capital outlay to deploy the network — incurred before operations begin.",
    ))
    flow.append(Spacer(1, 10))

    flow.append(_assumption_card(
        "Operating Expenditure (OpEx)",
        ACCENT_ORANGE,
        [
            ("Rent", f"{fmt_inr(opex['rent_per_station_monthly'])} / station / month"),
            ("Other station OpEx", f"{fmt_inr(opex['other_station_per_month'])} / station / month"),
            ("Network overhead", f"{fmt_inr(opex['overhead_monthly'])} / month"),
            ("Electricity", f"₹{opex['electricity_tariff_per_kwh']:.2f} / kWh charged"),
            ("Pack handling labour", f"₹{opex['labor_per_swap']:.2f} / swap"),
        ],
        subtitle="Recurring burn — fixed station overhead plus variable per-cycle costs.",
    ))
    flow.append(Spacer(1, 10))

    flow.append(_assumption_card(
        "Reliability Profile",
        ACCENT_BLUE,
        [
            ("Pack MTBF", f"{a['pack_mtbf_hours']:,.0f} hrs"),
            ("Pack MTTR", f"{a['pack_mttr_hours']:,.1f} hrs"),
            ("Charger MTBF", f"{a['charger_mtbf_hours']:,.0f} hrs"),
            ("Charger MTTR", f"{a['charger_mttr_hours']:,.1f} hrs"),
        ],
        subtitle="Hardware failure profile — mean time between failures and mean time to repair.",
    ))
    flow.append(Spacer(1, 10))

    risk = data["risk_knobs"]
    charger_dist_label = risk["charger_failure_distribution"]
    if charger_dist_label == "weibull":
        charger_dist_label = f"weibull (β = {risk['charger_weibull_shape']:.2f})"
    flow.append(_assumption_card(
        "Risk & Stress Assumptions",
        ACCENT_RED,
        [
            ("Range anxiety buffer", f"{risk['range_anxiety_buffer_pct'] * 100:.0f}% SoC"),
            ("Pack cycle degradation", f"{risk['cycle_degradation_rate_pct']:.3f}% SOH / cycle"),
            ("Pack calendar aging", f"{risk['calendar_aging_rate_pct_per_month']:.2f}% SOH / idle month"),
            ("Sabotage / loss rate", f"{risk['sabotage_pct_per_month'] * 100:.2f}% packs / month"),
            ("Charger failure model", charger_dist_label),
        ],
        subtitle="Behavioural and ageing stress applied to every projection.",
    ))

    return flow


def _attribution_block(data: dict[str, Any], styles: dict[str, ParagraphStyle]) -> list:
    note = (
        f"Generated by <font name='{FONT_BOLD}'>zng-network-sim</font> on "
        f"{data['generated_on']}. All figures derive from simulator outputs against "
        f"the configured scenario."
    )
    footer = Table(
        [[Paragraph(note, styles["footer_body"])]],
        colWidths=[PAGE_W],
        hAlign="LEFT",
    )
    footer.setStyle(TableStyle([
        ("LINEABOVE", (0, 0), (-1, 0), 0.75, BRAND_YELLOW),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return [Spacer(1, 16), footer]


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def build_unit_economics_pdf(
    scenario: Scenario,
    result: SimulationResult,
    bundle: FinanceBundle,
    mc_summary: MonteCarloSummary | None = None,
    scenario_name: str | None = None,
    today: date | None = None,
) -> bytes:
    """Render the unit economics PDF and return the raw bytes."""
    _register_fonts_once()
    data = _collect_report_data(scenario, result, bundle, mc_summary, scenario_name, today)
    styles = _styles()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=15 * mm, bottomMargin=15 * mm,
        title="Zunogo Unit Economics Report",
        author="zng-network-sim",
    )

    flowables: list = []
    flowables.extend(_cover_section(data, styles))
    flowables.extend(_input_parameters_section(data, styles))
    flowables.extend(_unit_economics_section(data, styles))
    flowables.extend(_attribution_block(data, styles))

    doc.build(flowables)
    return buf.getvalue()
