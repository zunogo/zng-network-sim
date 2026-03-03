"""Rendering functions for pitch deck slides in native Streamlit."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit as st

_ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets" / "deck"

# ---------------------------------------------------------------------------
# Tailwind-to-hex color map
# ---------------------------------------------------------------------------
C = {
    "yellow_300": "#fde68a",
    "yellow_400": "#facc15",
    "yellow_200": "#fef08a",
    "red_400": "#f87171",
    "blue_400": "#60a5fa",
    "blue_300": "#93c5fd",
    "green_400": "#4ade80",
    "green_300": "#86efac",
    "purple_400": "#c084fc",
    "purple_300": "#d8b4fe",
    "orange_400": "#fb923c",
    "cyan_400": "#22d3ee",
    "cyan_300": "#67e8f9",
    "gray_300": "#d1d5db",
    "gray_400": "#9ca3af",
    "gray_500": "#6b7280",
    "gray_800": "#1f2937",
    "white": "#ffffff",
    "red_300": "#fca5a5",
    # Background tints
    "red_bg": "rgba(127,29,29,0.2)",
    "blue_bg": "rgba(30,58,138,0.2)",
    "green_bg": "rgba(20,83,45,0.2)",
    "yellow_bg": "rgba(113,63,18,0.2)",
    "purple_bg": "rgba(88,28,135,0.2)",
    "orange_bg": "rgba(124,45,18,0.2)",
    "cyan_bg": "rgba(22,78,99,0.2)",
}


def _img_path(filename: str) -> str:
    return str(_ASSETS_DIR / filename)


def _highlight(text: str) -> str:
    return (
        f'<span style="background:#fde68a; color:#000; padding:2px 6px; '
        f'border-radius:4px; font-weight:500;">{text}</span>'
    )


def _styled_heading(text: str, size: str = "2rem", color: str = "#fff") -> str:
    return (
        f'<h2 style="font-family:Inter,sans-serif; font-size:{size}; '
        f'font-weight:700; color:{color}; margin-bottom:4px;">{text}</h2>'
    )


def _sub(text: str) -> str:
    return (
        f'<p style="color:{C["gray_300"]}; font-size:1rem; '
        f'margin-bottom:16px;">{text}</p>'
    )


def _card_html(
    title: str,
    body: str,
    accent: str = "#6c5ce7",
    bg: str = "rgba(31,41,55,1)",
) -> str:
    return f"""
    <div style="background:{bg}; border-radius:8px; padding:20px;
                border-top:3px solid {accent};">
        <h3 style="font-weight:700; color:{accent};
                    font-size:1.15rem; margin-bottom:10px;">{title}</h3>
        <div style="color:{C['gray_300']}; font-size:0.9rem;
                     line-height:1.6;">{body}</div>
    </div>
    """


def _bullet_list(items: list, highlight_indices: set[int] | None = None) -> str:
    highlight_indices = highlight_indices or set()
    parts: list[str] = []
    for i, item in enumerate(items):
        if isinstance(item, dict):
            txt = item["text"]
            if item.get("highlight"):
                txt = _highlight(txt)
            parts.append(f"<li>{txt}</li>")
        elif i in highlight_indices:
            parts.append(f"<li>{_highlight(item)}</li>")
        else:
            parts.append(f"<li>{item}</li>")
    return (
        f'<ul style="list-style:none; padding:0; margin:0; '
        f'color:{C["gray_300"]}; font-size:0.9rem; line-height:2;">'
        + "".join(parts)
        + "</ul>"
    )


# ===================================================================
# Layout renderers
# ===================================================================


def render_title(data: dict[str, Any]) -> None:
    st.markdown("<div style='height:40px;'></div>", unsafe_allow_html=True)
    if data.get("logo"):
        c1, c2, c3 = st.columns([1, 1, 1])
        with c2:
            st.image(_img_path(data["logo"]), width=180)
    heading_color = data.get("heading_color", C["yellow_300"])
    st.markdown(
        f'<h1 style="text-align:center; font-size:3rem; font-weight:700; '
        f'color:{heading_color};">{data["heading"]}</h1>',
        unsafe_allow_html=True,
    )
    tagline = data.get("tagline", "")
    if tagline:
        if data.get("tagline_style") == "highlight":
            tagline = _highlight(tagline)
        st.markdown(
            f'<p style="text-align:center; font-size:1.4rem; '
            f'font-style:italic; margin-top:12px;">{tagline}</p>',
            unsafe_allow_html=True,
        )
    subtitle = data.get("subtitle", "")
    if subtitle:
        st.markdown(
            f'<p style="text-align:center; color:{C["gray_400"]}; '
            f'font-size:1.1rem; margin-top:8px;">{subtitle}</p>',
            unsafe_allow_html=True,
        )


def render_two_col(data: dict[str, Any]) -> None:
    st.markdown(_styled_heading(data["heading"]), unsafe_allow_html=True)
    if data.get("subheading"):
        st.markdown(_sub(data["subheading"]), unsafe_allow_html=True)
    if data.get("intro"):
        st.markdown(
            f'<p style="color:{C["gray_300"]}; font-size:1rem; '
            f'margin-bottom:20px;">{data["intro"]}</p>',
            unsafe_allow_html=True,
        )

    left_col, right_col = st.columns(2)
    for col, side_key in [(left_col, "left"), (right_col, "right")]:
        side = data[side_key]
        with col:
            bg = side.get("bg", C["gray_800"])
            title_color = side.get("title_color", C["white"])
            bullets = _bullet_list(side["items"])
            html = _card_html(side["title"], bullets, accent=title_color, bg=bg)
            st.markdown(html, unsafe_allow_html=True)

    if data.get("footer"):
        st.markdown(
            f'<p style="color:{C["gray_300"]}; font-size:1rem; '
            f'margin-top:16px;">{data["footer"]}</p>',
            unsafe_allow_html=True,
        )


def render_two_col_quad(data: dict[str, Any]) -> None:
    """Two rows of two columns (for Zunogo's Opportunity slide)."""
    st.markdown(
        f'<p style="text-align:center; font-size:1.8rem; margin-bottom:20px;">'
        f'{_highlight(data["heading"])}</p>',
        unsafe_allow_html=True,
    )
    if data.get("subtitle"):
        st.markdown(
            f'<h3 style="text-align:center; color:{C["yellow_300"]}; '
            f'font-size:1.5rem; margin-bottom:20px;">{data["subtitle"]}</h3>',
            unsafe_allow_html=True,
        )
    rows = data["rows"]
    for row in rows:
        cols = st.columns(len(row))
        for col_st, card in zip(cols, row):
            with col_st:
                st.markdown(
                    _card_html(
                        card["title"],
                        f'<p>{card["body"]}</p>'
                        + (f'<p style="font-size:0.8rem; color:{C["gray_400"]}; '
                           f'margin-top:8px;">{card["detail"]}</p>'
                           if card.get("detail") else ""),
                        accent=card.get("accent", C["white"]),
                        bg=card.get("bg", C["gray_800"]),
                    ),
                    unsafe_allow_html=True,
                )
    if data.get("footer"):
        st.markdown(
            f'<p style="text-align:center; color:{C["yellow_200"]}; '
            f'font-size:1.1rem; margin-top:20px;">{data["footer"]}</p>',
            unsafe_allow_html=True,
        )


def render_stats_grid(data: dict[str, Any]) -> None:
    st.markdown(
        _styled_heading(data["heading"], size="2.2rem"),
        unsafe_allow_html=True,
    )
    if data.get("subheading"):
        st.markdown(
            f'<p style="text-align:center; color:{C["gray_300"]}; '
            f'margin-bottom:8px;">{data["subheading"]}</p>',
            unsafe_allow_html=True,
        )
    if data.get("highlight"):
        st.markdown(
            f'<p style="text-align:center; font-size:1.4rem; '
            f'margin-bottom:20px;">{_highlight(data["highlight"])}</p>',
            unsafe_allow_html=True,
        )

    for row in data["rows"]:
        cols = st.columns(len(row))
        for col_st, stat in zip(cols, row):
            with col_st:
                bg = stat.get("bg", C["gray_800"])
                num_color = stat.get("color", C["green_400"])
                st.markdown(
                    f'<div style="background:{bg}; border-radius:8px; '
                    f'padding:20px; text-align:center;">'
                    f'<div style="font-size:2rem; font-weight:700; '
                    f'color:{num_color};">{stat["value"]}</div>'
                    f'<p style="font-size:1rem; color:{C["white"]}; '
                    f'margin-top:4px;">{stat["label"]}</p>'
                    f'<p style="font-size:0.8rem; color:{C["gray_400"]}; '
                    f'margin-top:4px;">{stat.get("detail", "")}</p>'
                    f"</div>",
                    unsafe_allow_html=True,
                )


def render_image_grid(data: dict[str, Any]) -> None:
    if data.get("heading"):
        st.markdown(_styled_heading(data["heading"]), unsafe_allow_html=True)
    if data.get("subheading"):
        st.markdown(_sub(data["subheading"]), unsafe_allow_html=True)

    for row in data["rows"]:
        cols = st.columns(len(row))
        for col_st, item in zip(cols, row):
            with col_st:
                st.image(_img_path(item["image"]), use_container_width=True)
                if item.get("title"):
                    color = item.get("title_color", C["white"])
                    st.markdown(
                        f'<h4 style="color:{color}; font-weight:700; '
                        f'margin-top:8px;">{item["title"]}</h4>',
                        unsafe_allow_html=True,
                    )
                if item.get("subtitle"):
                    st.caption(item["subtitle"])
                if item.get("description"):
                    st.markdown(
                        f'<p style="color:{C["gray_300"]}; font-size:0.85rem;">'
                        f'{item["description"]}</p>',
                        unsafe_allow_html=True,
                    )
                if item.get("bullets"):
                    st.markdown(
                        _bullet_list(item["bullets"]),
                        unsafe_allow_html=True,
                    )


def render_table(data: dict[str, Any]) -> None:
    if data.get("heading"):
        st.markdown(
            _styled_heading(data["heading"], size="1.8rem"),
            unsafe_allow_html=True,
        )
    if data.get("subheading"):
        st.markdown(_sub(data["subheading"]), unsafe_allow_html=True)

    html = _build_table_html(
        data["headers"],
        data["rows"],
        data.get("header_colors"),
        data.get("highlight_col"),
    )
    st.markdown(html, unsafe_allow_html=True)

    if data.get("summary"):
        st.markdown(
            f'<p style="text-align:center; font-size:1.1rem; color:{C["yellow_300"]}; '
            f'font-weight:700; margin-top:16px;">{data["summary"]}</p>',
            unsafe_allow_html=True,
        )
    if data.get("summary_sub"):
        st.markdown(
            f'<p style="text-align:center; color:{C["gray_300"]}; '
            f'margin-top:4px;">{data["summary_sub"]}</p>',
            unsafe_allow_html=True,
        )

    if data.get("expander_title") and data.get("expander_table"):
        with st.expander(data["expander_title"]):
            exp = data["expander_table"]
            exp_html = _build_table_html(
                exp["headers"],
                exp["rows"],
                exp.get("header_colors"),
                exp.get("highlight_col"),
            )
            st.markdown(exp_html, unsafe_allow_html=True)


def _build_table_html(
    headers: list[dict],
    rows: list[dict],
    header_colors: list[str] | None = None,
    highlight_col: int | None = None,
) -> str:
    hc = header_colors or [C["white"]] * len(headers)
    parts = [
        '<div style="overflow-x:auto;">',
        '<table style="width:100%; border-collapse:collapse; font-size:0.85rem;">',
        "<thead><tr>",
    ]
    for i, h in enumerate(headers):
        color = hc[i] if i < len(hc) else C["white"]
        align = "left" if i == 0 else "center"
        parts.append(
            f'<th style="text-align:{align}; padding:10px; '
            f'color:{color}; font-weight:700; '
            f'border-bottom:1px solid {C["gray_500"]};">{h["label"]}</th>'
        )
    parts.append("</tr></thead><tbody>")

    for row in rows:
        bg = row.get("bg", "transparent")
        parts.append(f'<tr style="background:{bg}; border-bottom:1px solid rgba(75,85,99,0.3);">')
        for j, cell in enumerate(row["cells"]):
            align = "left" if j == 0 else "center"
            is_hl = highlight_col is not None and j == highlight_col
            cell_bg = "rgba(20,83,45,0.2)" if is_hl else "transparent"
            weight = "700" if row.get("bold") or is_hl else "400"
            color = C["white"] if is_hl or row.get("bold") else C["gray_300"]
            font_size = "1rem" if row.get("large") else "0.85rem"
            parts.append(
                f'<td style="text-align:{align}; padding:10px; '
                f'background:{cell_bg}; font-weight:{weight}; '
                f'color:{color}; font-size:{font_size};">{cell}</td>'
            )
        parts.append("</tr>")

    parts.append("</tbody></table></div>")
    return "".join(parts)


def render_cards_3col(data: dict[str, Any]) -> None:
    if data.get("heading"):
        st.markdown(_styled_heading(data["heading"]), unsafe_allow_html=True)
    if data.get("subheading"):
        st.markdown(_sub(data["subheading"]), unsafe_allow_html=True)

    cards = data["cards"]
    cols = st.columns(len(cards))
    for col_st, card in zip(cols, cards):
        with col_st:
            accent = card.get("accent", C["yellow_300"])
            body = ""
            if card.get("description"):
                body += f'<p>{card["description"]}</p>'
            if card.get("bullets"):
                body += _bullet_list(card["bullets"])
            st.markdown(
                _card_html(card["title"], body, accent=accent, bg=C["gray_800"]),
                unsafe_allow_html=True,
            )

    if data.get("footer"):
        st.markdown(
            f'<p style="text-align:center; color:{C["gray_300"]}; '
            f'margin-top:16px;">{data["footer"]}</p>',
            unsafe_allow_html=True,
        )


def render_team(data: dict[str, Any]) -> None:
    st.markdown(
        _styled_heading(data.get("heading", "The Team"), size="2.2rem"),
        unsafe_allow_html=True,
    )
    if data.get("subheading"):
        st.markdown(
            f'<p style="text-align:center; color:{C["gray_300"]}; '
            f'margin-bottom:20px;">{data["subheading"]}</p>',
            unsafe_allow_html=True,
        )

    members = data["members"]
    cols = st.columns(len(members))
    for col_st, m in zip(cols, members):
        with col_st:
            st.image(_img_path(m["photo"]), use_container_width=True)
            color = m.get("color", C["white"])
            st.markdown(
                f'<h4 style="color:{color}; font-weight:700; '
                f'margin-top:8px;">{m["name"]}</h4>',
                unsafe_allow_html=True,
            )
            for b in m.get("bullets", []):
                st.markdown(
                    f'<p style="font-size:0.75rem; color:{C["gray_300"]}; '
                    f'line-height:1.4; margin:2px 0;">{b}</p>',
                    unsafe_allow_html=True,
                )


def render_cta(data: dict[str, Any]) -> None:
    st.markdown("<div style='height:30px;'></div>", unsafe_allow_html=True)
    st.markdown(
        f'<h1 style="text-align:center; font-size:2.2rem; font-weight:700;">'
        f'{data["heading"]}</h1>',
        unsafe_allow_html=True,
    )
    if data.get("body"):
        st.markdown(
            f'<p style="text-align:center; font-size:1.2rem; '
            f'color:{C["gray_300"]}; margin:16px 0;">{data["body"]}</p>',
            unsafe_allow_html=True,
        )
    if data.get("contact_heading"):
        st.markdown(
            f'<div style="text-align:center; background:{C["gray_800"]}; '
            f'border-radius:8px; padding:30px; margin:20px auto; '
            f'max-width:500px;">'
            f'<h3 style="color:{C["blue_400"]}; font-size:1.5rem; '
            f'font-weight:700; margin-bottom:12px;">{data["contact_heading"]}</h3>'
            f'<p style="font-size:1.1rem; margin-bottom:12px;">'
            f'{data.get("contact_body", "")}</p>'
            f'<p style="color:{C["yellow_400"]}; font-size:1.3rem; '
            f'font-weight:700;">{data.get("email", "")}</p>'
            f"</div>",
            unsafe_allow_html=True,
        )
    if data.get("footer"):
        st.markdown(
            f'<p style="text-align:center; color:{C["gray_400"]}; '
            f'font-size:0.9rem; margin-top:12px;">{data["footer"]}</p>',
            unsafe_allow_html=True,
        )


def render_animated_html(data: dict[str, Any]) -> None:
    from .animation import ARCHITECTURE_ANIMATION_HTML

    st.html(ARCHITECTURE_ANIMATION_HTML)


def render_fleet_value(data: dict[str, Any]) -> None:
    """Custom renderer for Fleet Value slide (cards + SLA + responsibility)."""
    st.markdown(_styled_heading(data["heading"]), unsafe_allow_html=True)
    if data.get("subheading"):
        st.markdown(_sub(data["subheading"]), unsafe_allow_html=True)

    # Top cards
    cards = data.get("cards", [])
    if cards:
        cols = st.columns(len(cards))
        for col_st, card in zip(cols, cards):
            with col_st:
                st.markdown(
                    _card_html(
                        card["title"],
                        f'<p>{card["description"]}</p>',
                        accent=card.get("accent", C["yellow_300"]),
                        bg=C["gray_800"],
                    ),
                    unsafe_allow_html=True,
                )

    # SLA section
    sla = data.get("sla")
    if sla:
        st.markdown(
            f'<div style="background:{C["yellow_bg"]}; border-radius:8px; '
            f'padding:20px; margin-top:20px;">',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<h3 style="color:{C["yellow_300"]}; font-weight:700; '
            f'margin-bottom:12px;">{sla["title"]}</h3>',
            unsafe_allow_html=True,
        )
        sla_cols = st.columns(len(sla["metrics"]))
        for col_st, metric in zip(sla_cols, sla["metrics"]):
            with col_st:
                st.markdown(
                    f'<div style="background:rgba(17,24,39,0.3); '
                    f'border-radius:8px; padding:12px; text-align:center;">'
                    f'<p style="font-size:0.8rem; color:{C["gray_400"]}; '
                    f'margin-bottom:4px;">{metric["label"]}</p>'
                    f'<p style="font-size:1.4rem; font-weight:700; '
                    f'color:{C["white"]};">{metric["value"]}</p>'
                    f"</div>",
                    unsafe_allow_html=True,
                )
        if sla.get("note"):
            st.markdown(
                f'<p style="font-size:0.8rem; color:{C["gray_400"]}; '
                f'margin-top:8px;">{sla["note"]}</p>',
                unsafe_allow_html=True,
            )

        # Responsibility split
        resp = data.get("responsibility")
        if resp:
            st.markdown(
                f'<h3 style="color:{C["yellow_300"]}; font-weight:700; '
                f'margin:16px 0 8px;">{resp["title"]}</h3>',
                unsafe_allow_html=True,
            )
            resp_cols = st.columns(2)
            for col_st, side in zip(resp_cols, resp["sides"]):
                with col_st:
                    st.markdown(
                        f'<p style="font-weight:700; color:{C["white"]}; '
                        f'margin-bottom:4px;">{side["title"]}</p>',
                        unsafe_allow_html=True,
                    )
                    st.markdown(
                        _bullet_list(side["items"]),
                        unsafe_allow_html=True,
                    )

        st.markdown("</div>", unsafe_allow_html=True)


def render_oem_model(data: dict[str, Any]) -> None:
    """Custom renderer for OEM Model slide (multiple two-col sections)."""
    st.markdown(_styled_heading(data["heading"]), unsafe_allow_html=True)
    if data.get("subheading"):
        st.markdown(_sub(data["subheading"]), unsafe_allow_html=True)

    for section in data.get("sections", []):
        cols = st.columns(2)
        for col_st, panel in zip(cols, section):
            with col_st:
                body = ""
                if panel.get("items"):
                    if panel.get("ordered"):
                        items_html = "".join(f"<li>{it}</li>" for it in panel["items"])
                        body = (
                            f'<ol style="color:{C["gray_300"]}; font-size:0.9rem; '
                            f'line-height:2; padding-left:20px;">{items_html}</ol>'
                        )
                    else:
                        body = _bullet_list(panel["items"])
                if panel.get("note"):
                    body += (
                        f'<p style="color:{C["gray_400"]}; font-size:0.85rem; '
                        f'margin-top:8px;">{panel["note"]}</p>'
                    )
                st.markdown(
                    _card_html(
                        panel["title"],
                        body,
                        accent=panel.get("accent", C["yellow_300"]),
                        bg=C["gray_800"],
                    ),
                    unsafe_allow_html=True,
                )


# ===================================================================
# Dispatch
# ===================================================================

_RENDERERS = {
    "title": render_title,
    "two_col": render_two_col,
    "two_col_quad": render_two_col_quad,
    "stats_grid": render_stats_grid,
    "image_grid": render_image_grid,
    "table": render_table,
    "cards_3col": render_cards_3col,
    "team": render_team,
    "cta": render_cta,
    "animated_html": render_animated_html,
    "fleet_value": render_fleet_value,
    "oem_model": render_oem_model,
}


def dispatch(slide: Any) -> None:
    renderer = _RENDERERS.get(slide.layout)
    if renderer:
        renderer(slide.data)
    else:
        st.warning(f"Unknown slide layout: {slide.layout}")
