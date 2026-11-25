# Autonomous AI Agent Frameworks Hub (Master Blueprint)

This directory houses the foundational, production-grade repositories and standardized execution engines under Commander Aadarsh's **Autonomous AI Automation Ecosystem**.

---

## ⚡ Core Directive & Rules of Engagement

1. **Compulsory Browser Automation (`browser-use`)**:
   - For ANY and ALL web browsing, scraping, login workflows, DOM navigation, and web UI operations, **`browser-use` is STRICTLY COMPULSORY**.
   - Fragile scripts, raw Selenium, or naive clickers are strictly forbidden. Use `agent_frameworks.browser_use_engine.BrowserUseEngine` or the `./browser-use` repository.
2. **Mandatory Repository Reference**:
   - Whenever building, upgrading, or running an AI Agent, agents must reference the source code, patterns, and modules in `./agent_frameworks/` and `./browser-use/`.
3. **Zero-Latency Execution & Self-Healing**:
   - Closed-loop error feedback (Execute $\rightarrow$ Inspect $\rightarrow$ Patch $\rightarrow$ Re-run) is enforced via LangGraph state graphs.

---

## 📂 Cloned Repositories & Modules Overview

| Framework | Cloned Location | Primary Capability | Key Wrapper File |
| :--- | :--- | :--- | :--- |
| **browser-use** | `./browser-use` | **(COMPULSORY)** Vision + CDP web automation | `browser_use_engine.py` |
| **LangGraph** | `./agent_frameworks/langgraph` | Cyclic graphs, state machines, self-healing | `langgraph_self_healing.py` |
| **Mem0** | `./agent_frameworks/mem0` | Episodic, user profile, and vector memory | `mem0_memory_layer.py` |
| **CrewAI** | `./agent_frameworks/crewAI` | Role-based multi-agent swarms & delegation | `crewai_swarm_orchestrator.py` |
| **Instructor** | `./agent_frameworks/instructor` | Pydantic schema validation & auto-retry | `instructor_schema_guard.py` |
| **DSPy** | `./agent_frameworks/dspy` | Algorithmic prompt compiler & optimizer | `dspy_prompt_optimizer.py` |

---

## 🚀 Quick Usage Examples

### 1. Unified Master Engine Import
```python
from agent_frameworks.master_agent_hub import (
    MasterAgentEngine,
    BrowserUseEngine,
    SelfHealingCodeRunner,
    AgentMemoryHub,
    SchemaGuard,
    AgentSwarmHub,
)

engine = MasterAgentEngine(user_id="commander_aadarsh")
```

### 2. Mandatory Browser Automation (`browser-use`)
```python
import asyncio
from agent_frameworks.browser_use_engine import BrowserUseEngine
from langchain_google_genai import ChatGoogleGenerativeAI # or ChatOpenAI

async def run_browser():
    llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash")
    browser = BrowserUseEngine(headless=False)
    
    # Executes complex UI actions with vision spatial awareness
    history = await browser.execute_task(
        task_instruction="Go to Google, search for real estate CRM automations, and extract top 3 headlines",
        llm=llm
    )
    await browser.close()

asyncio.run(run_browser())
```

### 3. Self-Healing Cyclic Execution (`LangGraph`)
```python
from agent_frameworks.langgraph_self_healing import SelfHealingCodeRunner

runner = SelfHealingCodeRunner(max_retries=4)
result = runner.run(
    initial_code="print('Hello Commander Aadarsh')",
    task="Print greeting"
)
print("Success:", result["is_success"])
print("Output:", result["output"])
```

### 4. Memory Integration (`Mem0`)
```python
from agent_frameworks.mem0_memory_layer import AgentMemoryHub

memory = AgentMemoryHub()
memory.add_memory("All QBO sales receipts must have exact line amounts without calculations.")
context = memory.get_all_context()
```

### 5. Guaranteed Schema Outputs (`Instructor`)
```python
from agent_frameworks.instructor_schema_guard import SchemaGuard, LeadExtractionSchema

# Guarantees zero schema hallucination with auto-retry
guard = SchemaGuard(client=openai_client)
lead = guard.extract(
    response_model=LeadExtractionSchema,
    prompt="John Doe from Acme Corp, email john@acme.com, looking for a 50k automation contract."
)
```
