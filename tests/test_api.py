"""Tests for the LLM-accessible API layer (§10).

Covers:
  - Context manifest (compact + full)
  - Schema / defaults endpoints
  - Simulation endpoints (/simulate, /compare, /sensitivity, /optimize, /narrative)
  - Deep merge utility
  - Narrative generation
  - Tool definitions
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from zng_simulator.api.server import app, _deep_merge, _build_scenario
from zng_simulator.api.context import (
    build_context,
    get_scenario_schema,
    get_default_scenario,
    _extract_params,
)
from zng_simulator.api.narrative import generate_narrative, generate_comparison_narrative
from zng_simulator.api.tools import get_openai_tools, get_anthropic_tools, get_system_prompt
from zng_simulator.config.scenario import Scenario
from zng_simulator.config.vehicle import VehicleConfig


client = TestClient(app)


# ═══════════════════════════════════════════════════════════════════════════
# Context manifest tests
# ═══════════════════════════════════════════════════════════════════════════


class TestContext:
    """Tests for the context manifest generator."""

    def test_build_context_full(self):
        ctx = build_context("full")
        assert ctx.simulator_name == "ZNG Battery Swap Network Simulator"
        assert ctx.version == "2.0"
        assert len(ctx.business_model) > 100
        assert len(ctx.key_formulas) >= 5
        assert len(ctx.input_sections) == 10
        assert len(ctx.key_outputs) >= 10
        assert len(ctx.endpoints) >= 6
        assert len(ctx.interpretation_guide) > 100
        assert len(ctx.example_queries) >= 5

    def test_build_context_compact(self):
        ctx = build_context("compact")
        assert ctx.simulator_name == "ZNG Battery Swap Network Simulator"
        assert ctx.business_model == ""
        assert ctx.key_formulas == []
        assert ctx.interpretation_guide == ""
        assert ctx.example_queries == []
        # Sections still present
        assert len(ctx.input_sections) == 10
        assert len(ctx.key_outputs) >= 10

    def test_input_sections_have_parameters(self):
        ctx = build_context("compact")
        for section in ctx.input_sections:
            assert section.section, "Section name must not be empty"
            assert section.description, f"Section {section.section} has no description"
            assert len(section.parameters) > 0, f"Section {section.section} has no parameters"

    def test_parameter_info_structure(self):
        ctx = build_context("compact")
        # Check at least one param has constraints
        has_constraints = False
        for section in ctx.input_sections:
            for param in section.parameters:
                assert param.name
                assert param.type
                assert isinstance(param.description, str)
                if param.constraints:
                    has_constraints = True
        assert has_constraints, "Expected at least some params to have constraints"

    def test_get_scenario_schema(self):
        schema = get_scenario_schema()
        assert "properties" in schema
        assert "vehicle" in schema["properties"]
        assert "pack" in schema["properties"]

    def test_get_default_scenario(self):
        defaults = get_default_scenario()
        assert isinstance(defaults, dict)
        assert "vehicle" in defaults
        assert "pack" in defaults
        assert "simulation" in defaults
        # Verify defaults are valid
        scenario = Scenario(**defaults)
        assert scenario.simulation.horizon_months == 60

    def test_extract_params_from_model(self):
        params = _extract_params(VehicleConfig)
        names = [p.name for p in params]
        assert "packs_per_vehicle" in names
        assert "avg_daily_km" in names


# ═══════════════════════════════════════════════════════════════════════════
# Utility tests
# ═══════════════════════════════════════════════════════════════════════════


class TestUtilities:
    """Tests for helper utilities."""

    def test_deep_merge_simple(self):
        base = {"a": 1, "b": 2}
        overrides = {"b": 3, "c": 4}
        result = _deep_merge(base, overrides)
        assert result == {"a": 1, "b": 3, "c": 4}

    def test_deep_merge_nested(self):
        base = {"a": {"x": 1, "y": 2}, "b": 3}
        overrides = {"a": {"y": 99}}
        result = _deep_merge(base, overrides)
        assert result == {"a": {"x": 1, "y": 99}, "b": 3}

    def test_deep_merge_deep_nested(self):
        base = {"a": {"b": {"c": 1, "d": 2}}}
        overrides = {"a": {"b": {"c": 100}}}
        result = _deep_merge(base, overrides)
        assert result["a"]["b"]["c"] == 100
        assert result["a"]["b"]["d"] == 2

    def test_build_scenario_defaults(self):
        scenario = _build_scenario({})
        assert isinstance(scenario, Scenario)
        assert scenario.simulation.horizon_months == 60

    def test_build_scenario_overrides(self):
        scenario = _build_scenario({"revenue": {"price_per_swap": 99}})
        assert scenario.revenue.price_per_swap == 99
        # Other fields remain defaults
        assert scenario.simulation.horizon_months == 60


# ═══════════════════════════════════════════════════════════════════════════
# API endpoint tests (using TestClient — no server needed)
# ═══════════════════════════════════════════════════════════════════════════


class TestEndpoints:
    """Integration tests for FastAPI endpoints."""

    def test_root(self):
        resp = client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert "name" in data
        assert "start_here" in data

    def test_context_full(self):
        resp = client.get("/context?detail_level=full")
        assert resp.status_code == 200
        data = resp.json()
        assert data["simulator_name"] == "ZNG Battery Swap Network Simulator"
        assert len(data["business_model"]) > 100
        assert len(data["input_sections"]) == 10

    def test_context_compact(self):
        resp = client.get("/context?detail_level=compact")
        assert resp.status_code == 200
        data = resp.json()
        assert data["business_model"] == ""
        assert len(data["input_sections"]) == 10

    def test_context_default_is_full(self):
        resp = client.get("/context")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["business_model"]) > 100

    def test_schema(self):
        resp = client.get("/schema")
        assert resp.status_code == 200
        data = resp.json()
        assert "properties" in data

    def test_scenario_defaults(self):
        resp = client.get("/scenario/defaults")
        assert resp.status_code == 200
        data = resp.json()
        assert "vehicle" in data
        assert "simulation" in data

    def test_simulate_empty_body(self):
        """Default simulation — all defaults."""
        resp = client.post("/simulate", json={"scenario": {}})
        assert resp.status_code == 200
        data = resp.json()
        assert "result" in data
        assert "narrative" in data
        assert len(data["narrative"]) > 100
        # Check result structure
        result = data["result"]
        assert "summary" in result
        assert "cpc_waterfall" in result
        assert "months" in result

    def test_simulate_with_overrides(self):
        """Simulation with partial overrides."""
        resp = client.post("/simulate", json={
            "scenario": {
                "revenue": {"price_per_swap": 75},
                "simulation": {"horizon_months": 24},
            }
        })
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["result"]["months"]) == 24

    def test_simulate_stochastic(self):
        """Stochastic engine with Monte Carlo."""
        resp = client.post("/simulate", json={
            "scenario": {
                "simulation": {
                    "engine": "stochastic",
                    "monte_carlo_runs": 5,
                    "random_seed": 42,
                    "horizon_months": 12,
                },
            }
        })
        assert resp.status_code == 200
        data = resp.json()
        result = data["result"]
        assert result["engine_type"] == "stochastic"
        assert result["monte_carlo"] is not None

    def test_compare_chargers(self):
        """Compare two charger variants."""
        resp = client.post("/simulate/compare", json={
            "scenario": {"simulation": {"horizon_months": 12}},
            "charger_variants": [
                {"name": "Budget", "purchase_cost_per_slot": 8000, "rated_power_w": 1000, "mtbf_hours": 8000},
                {"name": "Premium", "purchase_cost_per_slot": 25000, "rated_power_w": 1000, "mtbf_hours": 40000},
            ],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["results"]) == 2
        assert len(data["ranking"]) == 2
        assert data["ranking"][0]["cpc_total"] <= data["ranking"][1]["cpc_total"]
        assert len(data["comparison_narrative"]) > 50

    def test_sensitivity(self):
        """Sensitivity analysis with default sweeps."""
        resp = client.post("/simulate/sensitivity", json={
            "scenario": {"simulation": {"horizon_months": 12}},
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "base_npv" in data
        assert "tornado_bars" in data
        assert len(data["tornado_bars"]) >= 1
        # Should be sorted by delta_npv descending
        deltas = [bar["delta_npv"] for bar in data["tornado_bars"]]
        assert deltas == sorted(deltas, reverse=True)

    def test_sensitivity_custom_sweeps(self):
        """Sensitivity analysis with custom sweep parameters."""
        resp = client.post("/simulate/sensitivity", json={
            "scenario": {"simulation": {"horizon_months": 12}},
            "sweep_params": [
                {"name": "Pack cost", "path": "pack.unit_cost", "low_pct": -0.20, "high_pct": 0.20},
            ],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["tornado_bars"]) == 1
        assert data["tornado_bars"][0]["param_name"] == "Pack cost"

    def test_optimize(self):
        """Fleet optimization (static engine for speed)."""
        resp = client.post("/simulate/optimize", json={
            "scenario": {"simulation": {"horizon_months": 12, "engine": "static"}},
            "target": "positive_ncf",
            "confidence_level_pct": 50.0,
            "min_fleet": 50,
            "max_fleet": 1000,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "recommended_fleet_size" in data
        assert "achieved" in data
        assert "narrative" in data

    def test_narrative_only(self):
        """Narrative-only endpoint."""
        resp = client.post("/simulate/narrative", json={
            "scenario": {"simulation": {"horizon_months": 12}},
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "narrative" in data
        assert "headline_metrics" in data
        assert "cost_per_cycle" in data["headline_metrics"]
        assert "break_even_month" in data["headline_metrics"]
        assert "npv" in data["headline_metrics"]

    def test_tools_openai(self):
        """OpenAI tool definitions endpoint."""
        resp = client.get("/tools/openai")
        assert resp.status_code == 200
        data = resp.json()
        assert "tools" in data
        assert "system_prompt" in data
        assert len(data["tools"]) >= 6
        # Verify structure
        for tool in data["tools"]:
            assert tool["type"] == "function"
            assert "name" in tool["function"]

    def test_tools_anthropic(self):
        """Anthropic tool definitions endpoint."""
        resp = client.get("/tools/anthropic")
        assert resp.status_code == 200
        data = resp.json()
        assert "tools" in data
        assert "system_prompt" in data
        assert len(data["tools"]) >= 6
        for tool in data["tools"]:
            assert "name" in tool
            assert "input_schema" in tool


# ═══════════════════════════════════════════════════════════════════════════
# Narrative tests
# ═══════════════════════════════════════════════════════════════════════════


class TestNarrative:
    """Tests for the narrative generator."""

    def test_narrative_from_static_result(self):
        from zng_simulator.engine.orchestrator import run_engine
        scenario = Scenario()
        charger = scenario.charger_variants[0]
        result = run_engine(scenario, charger)
        narrative = generate_narrative(result)
        assert "BUSINESS MODEL SUMMARY" in narrative
        assert "UNIT ECONOMICS" in narrative
        assert "FINANCIAL HEALTH" in narrative
        assert "RECOMMENDATIONS" in narrative
        assert len(narrative) > 200

    def test_narrative_mentions_charger(self):
        from zng_simulator.engine.orchestrator import run_engine
        scenario = Scenario()
        charger = scenario.charger_variants[0]
        result = run_engine(scenario, charger)
        narrative = generate_narrative(result)
        assert charger.name in narrative

    def test_comparison_narrative(self):
        from zng_simulator.engine.orchestrator import run_engine
        from zng_simulator.config.charger import ChargerVariant
        scenario = Scenario()
        c1 = ChargerVariant(name="Budget", mtbf_hours=8000)
        c2 = ChargerVariant(name="Premium", mtbf_hours=40000)
        r1 = run_engine(scenario, c1)
        r2 = run_engine(scenario, c2)
        narrative = generate_comparison_narrative([r1, r2])
        assert "CHARGER VARIANT COMPARISON" in narrative
        assert "Budget" in narrative
        assert "Premium" in narrative
        assert "Best option" in narrative


# ═══════════════════════════════════════════════════════════════════════════
# Tool definition tests
# ═══════════════════════════════════════════════════════════════════════════


class TestToolDefinitions:
    """Tests for LLM tool/function definitions."""

    def test_openai_tools_structure(self):
        tools = get_openai_tools()
        assert isinstance(tools, list)
        assert len(tools) >= 6
        for tool in tools:
            assert tool["type"] == "function"
            func = tool["function"]
            assert "name" in func
            assert "description" in func
            assert "parameters" in func

    def test_openai_tool_names(self):
        tools = get_openai_tools()
        names = {t["function"]["name"] for t in tools}
        expected = {
            "get_simulator_context",
            "get_default_scenario",
            "run_simulation",
            "compare_chargers",
            "run_sensitivity",
            "optimize_fleet_size",
            "get_narrative_only",
        }
        assert expected.issubset(names)

    def test_anthropic_tools_structure(self):
        tools = get_anthropic_tools()
        assert isinstance(tools, list)
        assert len(tools) >= 6
        for tool in tools:
            assert "name" in tool
            assert "description" in tool
            assert "input_schema" in tool

    def test_anthropic_matches_openai(self):
        openai_tools = get_openai_tools()
        anthropic_tools = get_anthropic_tools()
        assert len(openai_tools) == len(anthropic_tools)
        for ot, at in zip(openai_tools, anthropic_tools):
            assert ot["function"]["name"] == at["name"]

    def test_system_prompt(self):
        prompt = get_system_prompt()
        assert "ZNG" in prompt
        assert "battery swap" in prompt.lower()
        assert "run_simulation" in prompt
        assert len(prompt) > 200

    def test_system_prompt_custom_url(self):
        prompt = get_system_prompt("https://api.example.com")
        assert "https://api.example.com" in prompt
