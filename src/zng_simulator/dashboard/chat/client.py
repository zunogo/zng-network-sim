"""Anthropic client wrapper for the embedded chat interface."""

from __future__ import annotations

import json
import os
from typing import Any

import anthropic

from zng_simulator.api.tools import get_anthropic_tools
from zng_simulator.api.context import build_context


_SYSTEM_PROMPT = """You are an AI assistant embedded in the ZNG Battery Swap Network Simulator dashboard.

WHAT THE SIMULATOR DOES:
The ZNG simulator is a digital twin for commercial 2-wheeler battery swapping networks.
It models demand, battery degradation, charger reliability, and produces investor-grade
financial outputs (cost per cycle, NPV, IRR, DSCR, P&L, sensitivity analysis).

YOUR CAPABILITIES (tools you can call):
1. get_simulator_context — Read full simulator documentation (call first if unsure about parameters)
2. get_default_scenario — Get default input parameters as a starting point
3. run_simulation — Run a simulation with custom parameters
4. compare_chargers — Compare multiple charger variants head-to-head
5. run_sensitivity — Find which assumptions matter most to NPV
6. optimize_fleet_size — Find minimum fleet for financial targets
7. get_narrative_only — Get plain-English business interpretation

IMPORTANT CONTEXT:
- You are running INSIDE the dashboard. Your tool calls execute the simulation engine directly.
- Results are displayed as rich interactive charts and metric cards alongside your text.
- Keep your text responses focused on interpretation and business insights.
- Don't reproduce raw numbers that are already shown in the charts/cards.
- When the user asks follow-up questions, you can refer to previous simulation results.

WORKFLOW:
1. Understand the user's question
2. If needed, call get_simulator_context first to learn available parameters
3. Modify only relevant parameters (defaults are used for the rest)
4. Run the appropriate tool
5. Interpret results with business-actionable insights

KEY METRICS:
- Cost per cycle (CPC): headline unit economics — lower is better
- Break-even month: when cumulative cash flow turns positive
- NPV / IRR: overall project value and return
- DSCR: debt serviceability (>1.2 for lender comfort)
- Monte Carlo P10/P50/P90: uncertainty range

Always explain results in business terms. Focus on what the numbers mean and what to do about them.
"""


def get_api_key() -> str | None:
    """Get Anthropic API key from Streamlit secrets, environment, or .env file."""
    # 1. Streamlit secrets (Streamlit Cloud deployment)
    try:
        import streamlit as st
        key = st.secrets.get("ANTHROPIC_API_KEY")
        if key:
            return key
    except Exception:
        pass
    # 2. Environment variable
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return key
    # 3. .env file fallback (local dev)
    try:
        from dotenv import load_dotenv
        load_dotenv()
        key = os.environ.get("ANTHROPIC_API_KEY")
    except ImportError:
        pass
    return key


class ChatClient:
    """Wraps the Anthropic SDK for tool-use conversations."""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-20250514",
        sidebar_context: dict[str, Any] | None = None,
    ):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.tools = get_anthropic_tools()
        self.sidebar_context = sidebar_context
        self.system_prompt = self._build_system_prompt()

    def _build_system_prompt(self) -> str:
        context = build_context("compact")
        # Append a compact summary of available parameters
        sections_summary = []
        for section in context.input_sections:
            param_names = [p.name for p in section.parameters]
            sections_summary.append(
                f"  {section.section}: {', '.join(param_names)}"
            )
        params_text = "\n".join(sections_summary)
        prompt = (
            _SYSTEM_PROMPT
            + f"\n\nAVAILABLE INPUT PARAMETERS:\n{params_text}\n"
        )

        if self.sidebar_context:
            prompt += (
                "\n\nACTIVE SIMULATION CONTEXT:\n"
                "The user has already run a simulation from the dashboard sidebar. "
                "The results are loaded below (including full financial overlays: DCF, DSCR, P&L). "
                "When they ask follow-up questions, reference these results directly. "
                "You do NOT need to call run_simulation again unless the user wants to change parameters.\n\n"
                f"Scenario: {json.dumps(self.sidebar_context.get('scenario_summary', {}), default=str)}\n"
                f"Results: {json.dumps(self.sidebar_context.get('results', []), default=str)}\n"
            )
            if self.sidebar_context.get("pilot_sizing"):
                prompt += f"Pilot Sizing: {json.dumps(self.sidebar_context['pilot_sizing'], default=str)}\n"
            if self.sidebar_context.get("auto_tune"):
                prompt += f"Auto-Tune: {json.dumps(self.sidebar_context['auto_tune'], default=str)}\n"
            if self.sidebar_context.get("tuned_comparison"):
                prompt += f"Tuned vs Original: {json.dumps(self.sidebar_context['tuned_comparison'], default=str)}\n"

        return prompt

    def send_message(
        self,
        messages: list[dict[str, Any]],
    ) -> anthropic.types.Message:
        return self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=self.system_prompt,
            messages=messages,
            tools=self.tools,
        )
