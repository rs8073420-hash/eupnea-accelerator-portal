"""
========================================================================================
MASTER AGENT HUB (UNIFIED AUTONOMOUS AI FRAMEWORK)
========================================================================================
Central access point for all AI Agent development and execution in this workspace.

Rules & Architecture:
1. Browser Automation: BROWSER-USE IS COMPULSORY (BrowserUseEngine).
2. Cyclic Execution & Healing: LANGGRAPH (SelfHealingCodeRunner).
3. Persistent Memory: MEM0 (AgentMemoryHub).
4. Deterministic Output: INSTRUCTOR (SchemaGuard).
5. Algorithmic Prompts: DSPY (OptimizedAgentPipeline).
6. Swarm Teams: CREWAI (AgentSwarmHub).
========================================================================================
"""

import sys
from pathlib import Path

# Ensure agent_frameworks is in Python path
CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

# Import core modules
from browser_use_engine import BrowserUseEngine
from langgraph_self_healing import SelfHealingCodeRunner
from mem0_memory_layer import AgentMemoryHub
from instructor_schema_guard import SchemaGuard, LeadExtractionSchema
from dspy_prompt_optimizer import OptimizedAgentPipeline, configure_dspy
from crewai_swarm_orchestrator import AgentSwarmHub

__all__ = [
    "BrowserUseEngine",
    "SelfHealingCodeRunner",
    "AgentMemoryHub",
    "SchemaGuard",
    "LeadExtractionSchema",
    "OptimizedAgentPipeline",
    "configure_dspy",
    "AgentSwarmHub",
]

class MasterAgentEngine:
    """
    Unified controller providing one-call access to memory, browser, healing,
    and schema validation.
    """

    def __init__(self, user_id: str = "commander_aadarsh"):
        self.memory = AgentMemoryHub(user_id=user_id)
        self.browser_engine = BrowserUseEngine()
        self.code_runner = SelfHealingCodeRunner()
        self.schema_guard = SchemaGuard()

    def get_browser(self, headless: bool = False) -> BrowserUseEngine:
        """Returns the mandatory browser-use automation engine."""
        self.browser_engine.headless = headless
        return self.browser_engine

    def heal_code(self, initial_code: str, task: str):
        """Runs code in a cyclic self-healing loop until clean or max retries."""
        return self.code_runner.run(initial_code, task)

    def remember(self, observation: str):
        """Stores a persistent fact or rule in memory."""
        self.memory.add_memory(observation)

    def recall(self, query: str):
        """Recalls context related to query."""
        return self.memory.search_memories(query)


if __name__ == "__main__":
    hub = MasterAgentEngine()
    print("Master Agent Engine Ready.")
    print("All 6 Pillars connected and ready for autonomous agent execution.")
