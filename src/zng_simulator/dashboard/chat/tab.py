"""Chat tab UI — Claude-powered conversational interface for the simulator."""

from __future__ import annotations

import json
from typing import Any

import streamlit as st

from zng_simulator.dashboard.chat.client import ChatClient, get_api_key
from zng_simulator.dashboard.chat.executor import execute_tool
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
