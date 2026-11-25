"""
========================================================================================
LANGGRAPH SELF-HEALING EXECUTION PATTERN
========================================================================================
Implements a cyclic graph architecture:
Task Plan -> Code Execution -> Evaluation/Stderr Check -> [If Error: Self-Heal & Retry] -> Output
========================================================================================
"""

import sys
import subprocess
from typing import Dict, Any, List, TypedDict, Optional
from pathlib import Path

# Add langgraph repo to sys.path if needed
LANGGRAPH_REPO = Path(__file__).resolve().parent / "langgraph"
if str(LANGGRAPH_REPO) not in sys.path and LANGGRAPH_REPO.exists():
    sys.path.insert(0, str(LANGGRAPH_REPO))

try:
    from langgraph.graph import StateGraph, END
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False


class AgentState(TypedDict):
    task: str
    code: str
    error: Optional[str]
    output: Optional[str]
    iteration: int
    max_iterations: int
    is_success: bool


class SelfHealingCodeRunner:
    """
    Cyclic Self-Healing graph for code generation and runtime execution.
    """

    def __init__(self, llm_callable=None, max_retries: int = 4):
        self.llm = llm_callable
        self.max_retries = max_retries
        self.graph = self._build_graph()

    def _execute_code(self, state: AgentState) -> Dict[str, Any]:
        """Runs the generated code and captures stdout / stderr."""
        code = state["code"]
        iteration = state["iteration"] + 1

        print(f"[SelfHealing] Running iteration {iteration}...")

        try:
            result = subprocess.run(
                [sys.executable, "-c", code],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                print("[SelfHealing] Execution succeeded!")
                return {
                    "output": result.stdout,
                    "error": None,
                    "iteration": iteration,
                    "is_success": True,
                }
            else:
                print(f"[SelfHealing] Error detected: {result.stderr[:200]}")
                return {
                    "output": result.stdout,
                    "error": result.stderr,
                    "iteration": iteration,
                    "is_success": False,
                }
        except subprocess.TimeoutExpired:
            return {
                "output": None,
                "error": "TimeoutExpired: Execution exceeded 30 seconds limit.",
                "iteration": iteration,
                "is_success": False,
            }
        except Exception as e:
            return {
                "output": None,
                "error": str(e),
                "iteration": iteration,
                "is_success": False,
            }

    def _patch_code(self, state: AgentState) -> Dict[str, Any]:
        """Prompts the LLM to inspect the error and fix the code."""
        if not self.llm:
            # Fallback mock repair if LLM is not provided
            return {"code": state["code"]}

        prompt = (
            f"The following code failed execution:\n```python\n{state['code']}\n```\n\n"
            f"Runtime Error:\n{state['error']}\n\n"
            f"Task: {state['task']}\n\n"
            f"Please output the corrected Python code ONLY."
        )
        patched_code = self.llm(prompt)
        return {"code": patched_code}

    def _router(self, state: AgentState) -> str:
        """Route to finish or loop back to repair."""
        if state["is_success"]:
            return END
        if state["iteration"] >= state["max_iterations"]:
            print("[SelfHealing] Max iterations reached without clean pass.")
            return END
        return "patch_code"

    def _build_graph(self):
        if not LANGGRAPH_AVAILABLE:
            return None

        workflow = StateGraph(AgentState)
        workflow.add_node("execute_code", self._execute_code)
        workflow.add_node("patch_code", self._patch_code)

        workflow.set_entry_point("execute_code")
        workflow.add_conditional_edges(
            "execute_code",
            self._router,
            {"patch_code": "patch_code", END: END},
        )
        workflow.add_edge("patch_code", "execute_code")

        return workflow.compile()

    def run(self, initial_code: str, task: str) -> AgentState:
        initial_state: AgentState = {
            "task": task,
            "code": initial_code,
            "error": None,
            "output": None,
            "iteration": 0,
            "max_iterations": self.max_retries,
            "is_success": False,
        }

        if self.graph:
            return self.graph.invoke(initial_state)
        else:
            # Fallback loop without langgraph package
            curr = initial_state
            while curr["iteration"] < curr["max_iterations"] and not curr["is_success"]:
                res = self._execute_code(curr)
                curr.update(res)
                if not curr["is_success"] and curr["iteration"] < curr["max_iterations"]:
                    patch = self._patch_code(curr)
                    curr.update(patch)
            return curr


if __name__ == "__main__":
    print("LangGraph Self-Healing runner initialized.")
