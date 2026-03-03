"""Deck tab entry point: dropdown selector, slide navigation, rendering."""

from __future__ import annotations

import streamlit as st

from .renderers import C, dispatch
from .slides_fleet import FLEET_SLIDES
from .slides_investor import INVESTOR_SLIDES

_DECKS = {
    "Investor": INVESTOR_SLIDES,
    "Fleet & OEM": FLEET_SLIDES,
}


def render_deck_tab() -> None:
    deck_choice = st.selectbox(
        "Select Deck",
        list(_DECKS.keys()),
        key="deck_selector",
    )

    slides = _DECKS[deck_choice]

    if deck_choice != st.session_state.get("_deck_prev_choice"):
        st.session_state["deck_slide_idx"] = 0
        st.session_state["_deck_prev_choice"] = deck_choice

    if "deck_slide_idx" not in st.session_state:
        st.session_state["deck_slide_idx"] = 0

    total = len(slides)
    idx = max(0, min(st.session_state["deck_slide_idx"], total - 1))

    # ----- render current slide -----
    current = slides[idx]
    st.caption(f"**{current.title}**")
    dispatch(current)

    # ----- navigation bar -----
    st.divider()
    nav_prev, nav_dots, nav_next = st.columns([1, 6, 1])

    with nav_prev:
        if st.button("\u2190 Prev", disabled=(idx == 0), key="deck_prev"):
            st.session_state["deck_slide_idx"] = idx - 1
            st.rerun()

    with nav_dots:
        dots = " ".join(
            f'<span style="display:inline-block; width:8px; height:8px; '
            f"border-radius:50%; background:{'#9ca3af' if i == idx else '#4b5563'}; "
            f'margin:0 3px;"></span>'
            for i in range(total)
        )
        st.markdown(
            f'<div style="text-align:center; padding-top:6px;">'
            f"{dots}"
            f'<span style="display:block; color:{C["gray_500"]}; '
            f'font-size:0.7rem; margin-top:4px;">'
            f"{idx + 1} / {total}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )

    with nav_next:
        if st.button("Next \u2192", disabled=(idx == total - 1), key="deck_next"):
            st.session_state["deck_slide_idx"] = idx + 1
            st.rerun()
