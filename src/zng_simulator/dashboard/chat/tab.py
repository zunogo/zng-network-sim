"""Chat tab UI — Claude-powered conversational interface for the simulator."""

from __future__ import annotations

import copy
import json
from typing import Any

import streamlit as st

from zng_simulator.dashboard.chat.client import ChatClient, get_api_key
from zng_simulator.dashboard.chat.executor import attach_financials, condense_result, execute_tool
from zng_simulator.dashboard.chat.renderer import render_chat_result


# ═══════════════════════════════════════════════════════════════════════════
# Session state initialization
# ═══════════════════════════════════════════════════════════════════════════

def _init_state() -> None:
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []          # Anthropic API messages
    if "chat_display" not in st.session_state:
        st.session_state.chat_display = []            # UI display items
    if "chat_client" not in st.session_state:
        st.session_state.chat_client = None
    if "chat_input_tokens" not in st.session_state:
        st.session_state.chat_input_tokens = 0       # Cumulative input tokens
    if "chat_output_tokens" not in st.session_state:
        st.session_state.chat_output_tokens = 0      # Cumulative output tokens
    if "chat_api_calls" not in st.session_state:
        st.session_state.chat_api_calls = 0          # Number of API calls


def _clear_chat() -> None:
    st.session_state.chat_messages = []
    st.session_state.chat_display = []
    st.session_state.chat_input_tokens = 0
    st.session_state.chat_output_tokens = 0
    st.session_state.chat_api_calls = 0


def _build_sidebar_context() -> dict:
    """Build a compact context dict from sidebar simulation results.

    Attaches financial overlays (DCF, DSCR, statements) to the raw engine
    results so that condensed data includes NPV, IRR, and other finance metrics.
    """
    results = st.session_state.get("results", [])
    scenario = st.session_state.get("scenario")
    if not results or not scenario:
        return {}

    # Deep copy results to avoid mutating shared session state objects
    # attach_financials sets result.dcf, result.dscr etc. in-place
    enriched = []
    for r in results:
        r_copy = copy.deepcopy(r)
        cv = next(
            (c for c in scenario.charger_variants if c.name == r_copy.charger_variant_id),
            scenario.charger_variants[0],
        )
        enriched.append(attach_financials(r_copy, scenario, cv))

    # Compact scenario summary
    scenario_summary = {
        "fleet_size": scenario.revenue.initial_fleet_size,
        "horizon_months": scenario.simulation.horizon_months,
        "engine": scenario.simulation.engine,
        "vehicle": scenario.vehicle.name,
        "pack_cost": scenario.pack.unit_cost,
        "swap_price": scenario.revenue.price_per_swap,
        "num_stations": scenario.station.num_stations,
        "num_charger_variants": len(scenario.charger_variants),
    }

    ctx: dict[str, Any] = {
        "scenario_summary": scenario_summary,
        "results": [condense_result(r) for r in enriched],
    }

    # Intelligence tab: pilot sizing results
    ps_result = st.session_state.get("ps_result")
    if ps_result is not None:
        try:
            ctx["pilot_sizing"] = {
                "recommended_fleet": getattr(ps_result, "recommended_fleet_size", None),
                "target_metric": getattr(ps_result, "target_metric", None),
                "search_log": [
                    {
                        "fleet_size": entry.fleet_size,
                        "npv": entry.npv,
                        "break_even": entry.break_even_month,
                        "passed": entry.passed,
                    }
                    for entry in (getattr(ps_result, "search_log", None) or [])[:5]
                ],
            }
        except Exception:
            pass

    # Intelligence tab: auto-tune results
    tune_result = st.session_state.get("tune_result")
    if tune_result is not None:
        try:
            ctx["auto_tune"] = {
                "tuned_params": [
                    {
                        "name": p.param_path,
                        "original": p.original_value,
                        "tuned": p.tuned_value,
                        "confidence": p.confidence,
                    }
                    for p in (getattr(tune_result, "parameters", None) or [])
                ],
            }
        except Exception:
            pass

    # Intelligence tab: tuned comparison
    tuned_cmp = st.session_state.get("tuned_comparison")
    if tuned_cmp is not None:
        ctx["tuned_comparison"] = tuned_cmp

    return ctx


def _load_sidebar_context(api_key: str) -> None:
    """Load sidebar simulation context into chat, clearing any existing conversation."""
    sidebar_ctx = _build_sidebar_context()
    if not sidebar_ctx:
        return

    _clear_chat()

    # Recreate client with sidebar context in system prompt
    st.session_state.chat_client = ChatClient(
        api_key=api_key, sidebar_context=sidebar_ctx,
    )

    # Build a human-readable summary for display
    sc = sidebar_ctx["scenario_summary"]
    r0 = sidebar_ctx["results"][0]
    summary = r0.get("summary", {})
    cpc = r0.get("cpc_waterfall", {}).get("total", summary.get("avg_cost_per_cycle", 0))
    be = summary.get("break_even_month")
    be_str = f"month {be}" if be else "not reached"

    # Finance metrics (now available after attach_financials)
    dcf = r0.get("dcf", {}) or {}
    npv = dcf.get("npv", 0)
    irr = dcf.get("irr")
    irr_str = f"{irr * 100:.1f}%" if irr else "N/A"
    dscr = r0.get("dscr", {}) or {}
    avg_dscr = dscr.get("avg_dscr")
    dscr_str = f"{avg_dscr:.2f}" if avg_dscr else "N/A"

    context_text = (
        f"Loaded simulation: {sc['engine']} engine, "
        f"{sc['fleet_size']:,} vehicles, {sc['horizon_months']} months, "
        f"{sc['num_charger_variants']} charger variant(s). "
        f"CPC \u20b9{cpc:,.2f}, NPV \u20b9{npv:,.0f}, IRR {irr_str}, "
        f"DSCR {dscr_str}, break-even {be_str}."
    )

    # Add context banner to display
    st.session_state.chat_display.append({
        "type": "context_loaded",
        "content": context_text,
    })

    # Also include Intelligence tab data if available
    intel_context = ""
    if sidebar_ctx.get("pilot_sizing"):
        ps = sidebar_ctx["pilot_sizing"]
        intel_context += (
            f"\n\nPilot Sizing: recommended fleet = {ps.get('recommended_fleet', 'N/A')}, "
            f"target = {ps.get('target_metric', 'N/A')}"
        )
    if sidebar_ctx.get("auto_tune"):
        at = sidebar_ctx["auto_tune"]
        intel_context += (
            f"\n\nAuto-Tune: {len(at.get('tuned_params', []))} parameters calibrated from field data"
        )

    # Inject synthetic messages so Claude has the context in conversation history
    condensed_json = json.dumps(sidebar_ctx["results"], default=str)
    st.session_state.chat_messages.append({
        "role": "user",
        "content": (
            "I just ran a simulation from the dashboard sidebar. "
            f"Here are the results: {condensed_json}"
            + intel_context
        ),
    })
    st.session_state.chat_messages.append({
        "role": "assistant",
        "content": (
            f"I've loaded your simulation context. You ran a {sc['engine']} simulation "
            f"with {sc['fleet_size']:,} vehicles over {sc['horizon_months']} months. "
            f"Key results: CPC \u20b9{cpc:,.2f}/cycle, NPV \u20b9{npv:,.0f}, "
            f"IRR {irr_str}, DSCR {dscr_str}, break-even {be_str}. "
            "How can I help you explore further?"
        ),
    })

    # Show Claude's welcome as a display item
    st.session_state.chat_display.append({
        "type": "assistant",
        "content": (
            f"I've loaded your simulation context. You ran a **{sc['engine']}** simulation "
            f"with **{sc['fleet_size']:,}** vehicles over **{sc['horizon_months']}** months.\n\n"
            f"| Metric | Value |\n|--------|-------|\n"
            f"| CPC | \u20b9{cpc:,.2f}/cycle |\n"
            f"| NPV | \u20b9{npv:,.0f} |\n"
            f"| IRR | {irr_str} |\n"
            f"| DSCR | {dscr_str} |\n"
            f"| Break-even | {be_str} |\n"
            f"| Swap Price | \u20b9{sc['swap_price']}/visit |\n\n"
            "How can I help you explore further?"
        ),
    })


# ═══════════════════════════════════════════════════════════════════════════
# Message processing (agentic tool-use loop)
# ═══════════════════════════════════════════════════════════════════════════

def _process_message(user_input: str) -> None:
    """Run the agentic loop: send to Claude, handle tool calls, collect results."""
    client: ChatClient = st.session_state.chat_client

    # Add user message
    st.session_state.chat_messages.append({
        "role": "user",
        "content": user_input,
    })
    st.session_state.chat_display.append({
        "type": "user",
        "content": user_input,
    })

    # Agentic loop
    max_iterations = 10
    for _ in range(max_iterations):
        try:
            response = client.send_message(st.session_state.chat_messages)
        except Exception as e:
            st.session_state.chat_display.append({
                "type": "error",
                "content": f"API error: {e}",
            })
            return

        # Track token usage
        st.session_state.chat_api_calls += 1
        if hasattr(response, "usage") and response.usage:
            st.session_state.chat_input_tokens += response.usage.input_tokens
            st.session_state.chat_output_tokens += response.usage.output_tokens

        # Add assistant response to conversation history
        st.session_state.chat_messages.append({
            "role": "assistant",
            "content": response.content,
        })

        if response.stop_reason == "end_turn":
            # Extract text blocks for display
            for block in response.content:
                if hasattr(block, "text") and block.text.strip():
                    st.session_state.chat_display.append({
                        "type": "assistant",
                        "content": block.text,
                    })
            return

        if response.stop_reason == "tool_use":
            tool_results_for_api: list[dict[str, Any]] = []

            for block in response.content:
                if hasattr(block, "text") and block.text and block.text.strip():
                    st.session_state.chat_display.append({
                        "type": "assistant",
                        "content": block.text,
                    })

                if block.type == "tool_use":
                    # Show thinking indicator
                    st.session_state.chat_display.append({
                        "type": "thinking",
                        "tool_name": block.name,
                    })

                    # Execute tool locally
                    result_data, sim_result = execute_tool(block.name, block.input)

                    # Store for rich rendering (only for tools that return sim results)
                    if sim_result is not None:
                        st.session_state.chat_display.append({
                            "type": "tool_result",
                            "tool_name": block.name,
                            "data": result_data,
                            "sim_result": sim_result,
                        })
                    elif block.name == "run_sensitivity":
                        # Sensitivity has no SimulationResult but has chart data
                        st.session_state.chat_display.append({
                            "type": "tool_result",
                            "tool_name": block.name,
                            "data": result_data,
                            "sim_result": None,
                        })

                    # Prepare condensed result for Claude
                    tool_results_for_api.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result_data, default=str),
                    })

            # Send tool results back to Claude
            st.session_state.chat_messages.append({
                "role": "user",
                "content": tool_results_for_api,
            })
            continue

        # Unexpected stop reason — just extract text and stop
        for block in response.content:
            if hasattr(block, "text") and block.text.strip():
                st.session_state.chat_display.append({
                    "type": "assistant",
                    "content": block.text,
                })
        return


# ═══════════════════════════════════════════════════════════════════════════
# Rendering
# ═══════════════════════════════════════════════════════════════════════════

def _render_display() -> None:
    """Render all display items from session state."""
    for item in st.session_state.chat_display:
        item_type = item["type"]

        if item_type == "user":
            with st.chat_message("user"):
                st.markdown(item["content"])

        elif item_type == "assistant":
            with st.chat_message("assistant"):
                st.markdown(item["content"])

        elif item_type == "thinking":
            with st.chat_message("assistant"):
                st.caption(f"🔧 Called `{item['tool_name']}`")

        elif item_type == "tool_result":
            with st.chat_message("assistant"):
                render_chat_result(
                    item["tool_name"],
                    item["data"],
                    item.get("sim_result"),
                )

        elif item_type == "context_loaded":
            st.info(item["content"])

        elif item_type == "error":
            with st.chat_message("assistant"):
                st.error(item["content"])


# ═══════════════════════════════════════════════════════════════════════════
# Main entry point
# ═══════════════════════════════════════════════════════════════════════════

def render_chat_tab() -> None:
    """Render the Chat tab contents."""
    _init_state()

    # Check for API key
    api_key = get_api_key()
    if not api_key:
        st.markdown("""
        <div style="
            background: linear-gradient(135deg, rgba(108,92,231,0.10), rgba(9,132,227,0.06));
            border: 1px solid rgba(108,92,231,0.18);
            border-radius: 10px;
            padding: 48px 32px;
            text-align: center;
            margin: 2rem 0;
        ">
            <div style="font-size: 2rem; margin-bottom: 6px;">🤖</div>
            <div style="font-family: 'Inter', sans-serif; font-size: 1.15rem; font-weight: 700; color: #fff; margin-bottom: 4px; letter-spacing: -0.3px;">Chat Unavailable</div>
            <div style="font-family: 'Inter', sans-serif; color: rgba(255,255,255,0.42); font-size: 0.82rem; font-weight: 400;">
                Set <code>ANTHROPIC_API_KEY</code> environment variable to enable the AI chat assistant.
            </div>
        </div>
        """, unsafe_allow_html=True)
        return

    # Initialize client if needed
    if st.session_state.chat_client is None:
        st.session_state.chat_client = ChatClient(api_key=api_key)

    # Check for pending sidebar context (from "Continue in Chat" button)
    if st.session_state.pop("chat_sidebar_pending", False):
        _load_sidebar_context(api_key)
        # Auto-switch to Chat tab via JS (Streamlit has no native tab switch API)
        st.components.v1.html(
            """<script>
            const tabs = window.parent.document.querySelectorAll('[data-baseweb="tab"]');
            if (tabs.length >= 4) tabs[3].click();
            </script>""",
            height=0,
        )

    # Header
    col1, col2 = st.columns([4, 1])
    with col1:
        st.caption("Ask questions about your battery swap network in natural language.")
    with col2:
        if st.button("Clear Chat", use_container_width=True):
            _clear_chat()
            st.rerun()

    # Render chat history or welcome message
    if not st.session_state.chat_display:
        with st.chat_message("assistant"):
            st.markdown(
                "Hi! I'm your battery swap network analyst. "
                "Ask me anything — for example:\n\n"
                '- *"Run a default simulation"*\n'
                '- *"What if pack cost drops to 10,000?"*\n'
                '- *"Compare budget vs premium chargers"*\n'
                '- *"Which parameters affect NPV the most?"*\n'
                '- *"What\'s the minimum fleet for positive cash flow?"*'
            )
    else:
        _render_display()

    # Chat input
    if user_input := st.chat_input("Ask about your battery swap network..."):
        with st.spinner("Thinking..."):
            _process_message(user_input)
        st.rerun()

    # API usage metrics
    total_input = st.session_state.chat_input_tokens
    total_output = st.session_state.chat_output_tokens
    total_calls = st.session_state.chat_api_calls
    if total_calls > 0:
        total_tokens = total_input + total_output
        # Sonnet pricing: $3/M input, $15/M output
        est_cost = (total_input * 3 + total_output * 15) / 1_000_000
        st.markdown(f"""
        <div style="
            display: flex; gap: 24px; align-items: center;
            padding: 8px 16px; margin-top: 12px;
            background: rgba(108,92,231,0.06);
            border: 1px solid rgba(108,92,231,0.12);
            border-radius: 8px;
            font-family: 'Inter', sans-serif;
            font-size: 0.75rem; color: rgba(255,255,255,0.45);
        ">
            <span>API calls: <b style="color:rgba(255,255,255,0.7)">{total_calls}</b></span>
            <span>Input: <b style="color:rgba(255,255,255,0.7)">{total_input:,}</b> tokens</span>
            <span>Output: <b style="color:rgba(255,255,255,0.7)">{total_output:,}</b> tokens</span>
            <span>Total: <b style="color:rgba(255,255,255,0.7)">{total_tokens:,}</b> tokens</span>
            <span>Est. cost: <b style="color:rgba(255,255,255,0.7)">${est_cost:.4f}</b></span>
        </div>
        """, unsafe_allow_html=True)
