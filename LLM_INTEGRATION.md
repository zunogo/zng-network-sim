# LLM Integration Guide

Your API is live at: **`https://zng-simulator-api.onrender.com`**

---

## Quick Start (3 steps)

### Step 1: Get the context (LLM reads this first)

```python
import requests

API_URL = "https://zng-simulator-api.onrender.com"

# Get full context (business model + schemas + interpretation guide)
context = requests.get(f"{API_URL}/context?detail_level=full").json()
print(f"Context size: ~{len(str(context)):,} chars")
```

### Step 2: Get tool definitions

```python
# For OpenAI
openai_tools = requests.get(f"{API_URL}/tools/openai").json()
tools = openai_tools["tools"]
system_prompt = openai_tools["system_prompt"]

# For Anthropic
anthropic_tools = requests.get(f"{API_URL}/tools/anthropic").json()
tools = anthropic_tools["tools"]
system_prompt = anthropic_tools["system_prompt"]
```

### Step 3: Connect the LLM

See examples below for OpenAI and Anthropic.

---

## Example 1: OpenAI (GPT-4o)

```python
from openai import OpenAI
import requests
import json

API_URL = "https://zng-simulator-api.onrender.com"
client = OpenAI(api_key="your-openai-key")

# Get tools and system prompt
openai_config = requests.get(f"{API_URL}/tools/openai").json()
tools = openai_config["tools"]
system_prompt = openai_config["system_prompt"]

# Helper function to map OpenAI function calls to API endpoints
def call_simulator_api(function_name: str, arguments: dict):
    """Map OpenAI function calls to actual API endpoints."""
    if function_name == "get_simulator_context":
        detail = arguments.get("detail_level", "full")
        return requests.get(f"{API_URL}/context?detail_level={detail}").json()
    
    elif function_name == "get_default_scenario":
        return requests.get(f"{API_URL}/scenario/defaults").json()
    
    elif function_name == "run_simulation":
        scenario = arguments.get("scenario", {})
        resp = requests.post(f"{API_URL}/simulate", json={"scenario": scenario})
        return resp.json()
    
    elif function_name == "compare_chargers":
        scenario = arguments.get("scenario", {})
        charger_variants = arguments.get("charger_variants", [])
        resp = requests.post(
            f"{API_URL}/simulate/compare",
            json={"scenario": scenario, "charger_variants": charger_variants}
        )
        return resp.json()
    
    elif function_name == "run_sensitivity":
        scenario = arguments.get("scenario", {})
        sweep_params = arguments.get("sweep_params")
        resp = requests.post(
            f"{API_URL}/simulate/sensitivity",
            json={"scenario": scenario, "sweep_params": sweep_params}
        )
        return resp.json()
    
    elif function_name == "optimize_fleet_size":
        scenario = arguments.get("scenario", {})
        target = arguments.get("target", "positive_ncf")
        confidence = arguments.get("confidence_level", 0.5)
        resp = requests.post(
            f"{API_URL}/simulate/optimize",
            json={
                "scenario": scenario,
                "target": target,
                "confidence_level_pct": confidence * 100,
            }
        )
        return resp.json()
    
    elif function_name == "get_narrative_only":
        scenario = arguments.get("scenario", {})
        resp = requests.post(f"{API_URL}/simulate/narrative", json={"scenario": scenario})
        return resp.json()
    
    else:
        return {"error": f"Unknown function: {function_name}"}


# Start conversation
messages = [
    {"role": "system", "content": system_prompt},
    {"role": "user", "content": "What happens if we reduce pack cost by 20%?"}
]

response = client.chat.completions.create(
    model="gpt-4o",
    messages=messages,
    tools=tools,
    tool_choice="auto",
)

# Handle function calls
message = response.choices[0].message
if message.tool_calls:
    for tool_call in message.tool_calls:
        function_name = tool_call.function.name
        arguments = json.loads(tool_call.function.arguments)
        
        # Call the API
        result = call_simulator_api(function_name, arguments)
        
        # Add result back to conversation
        messages.append(message)
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": json.dumps(result),
        })
    
    # Get final response
    final_response = client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        tools=tools,
    )
    print(final_response.choices[0].message.content)
else:
    print(message.content)
```

---

## Example 2: Anthropic (Claude)

```python
import anthropic
import requests
import json

API_URL = "https://zng-simulator-api.onrender.com"
client = anthropic.Anthropic(api_key="your-anthropic-key")

# Get tools and system prompt
anthropic_config = requests.get(f"{API_URL}/tools/anthropic").json()
tools = anthropic_config["tools"]
system_prompt = anthropic_config["system_prompt"]

# Helper function (same as OpenAI example above)
def call_simulator_api(function_name: str, arguments: dict):
    # ... (same implementation as OpenAI example)
    pass

# Start conversation
message = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=4096,
    system=system_prompt,
    messages=[
        {"role": "user", "content": "Compare a budget charger vs premium charger"}
    ],
    tools=tools,
)

# Handle tool use
if message.stop_reason == "tool_use":
    tool_use = message.content[0]
    function_name = tool_use.name
    arguments = tool_use.input
    
    # Call the API
    result = call_simulator_api(function_name, arguments)
    
    # Continue conversation with result
    final_message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        system=system_prompt,
        messages=[
            {"role": "user", "content": "Compare a budget charger vs premium charger"},
            message,
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": json.dumps(result),
                    }
                ],
            },
        ],
        tools=tools,
    )
    print(final_message.content[0].text)
else:
    print(message.content[0].text)
```

---

## Example 3: LangChain (Universal)

```python
from langchain_openai import ChatOpenAI
from langchain.tools import tool
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
import requests

API_URL = "https://zng-simulator-api.onrender.com"

# Get system prompt
system_prompt = requests.get(f"{API_URL}/tools/openai").json()["system_prompt"]

# Define tools as LangChain tools
@tool
def run_simulation(scenario: dict = None) -> dict:
    """Run a battery swap network simulation."""
    resp = requests.post(f"{API_URL}/simulate", json={"scenario": scenario or {}})
    return resp.json()

@tool
def compare_chargers(scenario: dict, charger_variants: list) -> dict:
    """Compare multiple charger variants."""
    resp = requests.post(
        f"{API_URL}/simulate/compare",
        json={"scenario": scenario, "charger_variants": charger_variants}
    )
    return resp.json()

@tool
def get_context(detail_level: str = "full") -> dict:
    """Get simulator context (business model, schemas, etc.)."""
    return requests.get(f"{API_URL}/context?detail_level={detail_level}").json()

# Create agent
llm = ChatOpenAI(model="gpt-4o", temperature=0)
tools = [run_simulation, compare_chargers, get_context]

prompt = ChatPromptTemplate.from_messages([
    ("system", system_prompt),
    ("human", "{input}"),
    MessagesPlaceholder(variable_name="agent_scratchpad"),
])

agent = create_openai_tools_agent(llm, tools, prompt)
executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

# Run
result = executor.invoke({"input": "What if pack cost drops 20%?"})
print(result["output"])
```

---

## Example 4: Simple REST Client (Any LLM Framework)

If your LLM framework doesn't support function calling, you can manually construct API calls:

```python
import requests

API_URL = "https://zng-simulator-api.onrender.com"

# Step 1: LLM reads context
context = requests.get(f"{API_URL}/context?detail_level=full").json()
# Send context to LLM as system prompt (or first message)

# Step 2: LLM decides what to do, you call the API
# Example: User asks "What if pack cost is 10,000?"
# You call:
result = requests.post(
    f"{API_URL}/simulate",
    json={"scenario": {"pack": {"unit_cost": 10000}}}
).json()

# Step 3: Send narrative back to LLM
narrative = result["narrative"]
# LLM interprets and responds to user
```

---

## Testing the Connection

Quick test to verify everything works:

```python
import requests

API_URL = "https://zng-simulator-api.onrender.com"

# Health check
print("Health:", requests.get(f"{API_URL}/health").json())

# Get context
context = requests.get(f"{API_URL}/context").json()
print(f"Context loaded: {len(context['input_sections'])} input sections")

# Get tools
tools = requests.get(f"{API_URL}/tools/openai").json()
print(f"Tools loaded: {len(tools['tools'])} functions")

# Run a simple simulation
result = requests.post(f"{API_URL}/simulate", json={"scenario": {}}).json()
print(f"Simulation complete: CPC = ₹{result['result']['cpc_waterfall']['total']:.2f}/cycle")
print(f"Narrative length: {len(result['narrative'])} chars")
```

---

## Key Endpoints for LLMs

| Endpoint | Purpose |
|----------|---------|
| `GET /context?detail_level=full` | **Read first** — full business model + schemas |
| `GET /tools/openai` | Pre-built function definitions for OpenAI |
| `GET /tools/anthropic` | Pre-built tool definitions for Anthropic |
| `POST /simulate` | Run simulation (returns results + narrative) |
| `POST /simulate/narrative` | Lightweight: narrative only |
| `POST /simulate/compare` | Compare charger variants |
| `POST /simulate/sensitivity` | Parameter sweep → tornado chart |
| `POST /simulate/optimize` | Find minimum fleet size |

---

## Tips

1. **Always call `/context` first** — it's the "system prompt" for the simulator
2. **Use `/simulate/narrative`** for lightweight responses when you only need interpretation
3. **The narrative is LLM-friendly** — it's structured plain English, perfect for LLMs to reason about
4. **Handle cold starts** — Render free tier spins down after 15 min, first request takes ~30s

---

## Next Steps

1. Test the connection with the examples above
2. Integrate into your LLM application
3. Monitor usage — Render free tier has limits
4. Consider upgrading to Render paid ($7/mo) for always-on if needed
