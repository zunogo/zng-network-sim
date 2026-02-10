#!/usr/bin/env python3
"""Quick test script to verify LLM connection to deployed API."""

import requests
import json

API_URL = "https://zng-simulator-api.onrender.com"

print("=" * 60)
print("Testing LLM Connection to ZNG Simulator API")
print("=" * 60)
print()

# 1. Health check
print("1. Health check...")
try:
    health = requests.get(f"{API_URL}/health", timeout=10)
    print(f"   ✓ Status: {health.status_code}")
    print(f"   ✓ Response: {health.json()}")
except Exception as e:
    print(f"   ✗ Failed: {e}")
    exit(1)
print()

# 2. Get context (what LLM reads first)
print("2. Getting context (full)...")
try:
    context = requests.get(f"{API_URL}/context?detail_level=full", timeout=30)
    ctx_data = context.json()
    print(f"   ✓ Status: {context.status_code}")
    print(f"   ✓ Simulator: {ctx_data['simulator_name']}")
    print(f"   ✓ Input sections: {len(ctx_data['input_sections'])}")
    print(f"   ✓ Key outputs: {len(ctx_data['key_outputs'])}")
    print(f"   ✓ Endpoints: {len(ctx_data['endpoints'])}")
    print(f"   ✓ Size: ~{len(json.dumps(ctx_data)):,} chars")
except Exception as e:
    print(f"   ✗ Failed: {e}")
    exit(1)
print()

# 3. Get OpenAI tools
print("3. Getting OpenAI tool definitions...")
try:
    tools = requests.get(f"{API_URL}/tools/openai", timeout=10)
    tools_data = tools.json()
    print(f"   ✓ Status: {tools.status_code}")
    print(f"   ✓ Tools: {len(tools_data['tools'])}")
    print(f"   ✓ System prompt length: {len(tools_data['system_prompt'])} chars")
    print(f"   ✓ Tool names: {[t['function']['name'] for t in tools_data['tools']]}")
except Exception as e:
    print(f"   ✗ Failed: {e}")
    exit(1)
print()

# 4. Run a simple simulation
print("4. Running test simulation...")
try:
    result = requests.post(
        f"{API_URL}/simulate",
        json={"scenario": {"simulation": {"horizon_months": 12}}},
        timeout=60
    )
    sim_data = result.json()
    print(f"   ✓ Status: {result.status_code}")
    print(f"   ✓ Cost per cycle: ₹{sim_data['result']['cpc_waterfall']['total']:.2f}")
    print(f"   ✓ Break-even month: {sim_data['result']['summary']['break_even_month']}")
    print(f"   ✓ Narrative length: {len(sim_data['narrative'])} chars")
    print(f"   ✓ Narrative preview:")
    print(f"     {sim_data['narrative'][:200]}...")
except Exception as e:
    print(f"   ✗ Failed: {e}")
    exit(1)
print()

# 5. Get narrative only (lightweight)
print("5. Testing narrative-only endpoint...")
try:
    narrative = requests.post(
        f"{API_URL}/simulate/narrative",
        json={"scenario": {}},
        timeout=60
    )
    narr_data = narrative.json()
    print(f"   ✓ Status: {narrative.status_code}")
    print(f"   ✓ Headline metrics:")
    for key, val in narr_data["headline_metrics"].items():
        print(f"     - {key}: {val}")
except Exception as e:
    print(f"   ✗ Failed: {e}")
    exit(1)
print()

print("=" * 60)
print("✓ All tests passed! API is ready for LLM integration.")
print("=" * 60)
print()
print("Next steps:")
print("1. See LLM_INTEGRATION.md for OpenAI/Anthropic examples")
print("2. Use the tools from /tools/openai or /tools/anthropic")
print("3. Start with GET /context to give LLM full understanding")
