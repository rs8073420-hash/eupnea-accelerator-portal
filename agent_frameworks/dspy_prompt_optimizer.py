"""
========================================================================================
DSPY ALGORITHMIC PROMPT COMPILER & OPTIMIZER
========================================================================================
Replaces brittle manual prompt engineering with compiled, metrics-driven pipelines.
Optimizes signatures, few-shot examples, and instructions programmatically.
========================================================================================
"""

import sys
from pathlib import Path
from typing import Any, Optional

# Add dspy repo to sys.path if needed
DSPY_REPO = Path(__file__).resolve().parent / "dspy"
if str(DSPY_REPO) not in sys.path and DSPY_REPO.exists():
    sys.path.insert(0, str(DSPY_REPO))

try:
    import dspy
    from dspy.teleprompt import BootstrapFewShot
    DSPY_AVAILABLE = True
except ImportError:
    DSPY_AVAILABLE = False


class AgentSignature(dspy.Signature if DSPY_AVAILABLE else object):
    """
    Standard DSPy signature: Takes user task and context, produces reasoned action plan.
    """
    if DSPY_AVAILABLE:
        context = dspy.InputField(desc="Relevant rules, schema, and past memories")
        task = dspy.InputField(desc="The automation task to execute")
        reasoning = dspy.OutputField(desc="Step-by-step logic and validation checks")
        action_plan = dspy.OutputField(desc="Final executable script or action steps")


class OptimizedAgentPipeline(dspy.Module if DSPY_AVAILABLE else object):
    """
    DSPy module using ChainOfThought reasoning.
    """
    def __init__(self):
        super().__init__()
        if DSPY_AVAILABLE:
            self.generate_plan = dspy.ChainOfThought(AgentSignature)

    def forward(self, context: str, task: str):
        if not DSPY_AVAILABLE:
            raise RuntimeError("DSPy is not available in the environment.")
        return self.generate_plan(context=context, task=task)


def configure_dspy(lm_model: str = "openai/gpt-4o-mini", api_key: Optional[str] = None):
    """Initializes DSPy LM runtime."""
    if not DSPY_AVAILABLE:
        print("[DSPy] Package not installed. Install via pip install dspy-ai")
        return None
    lm = dspy.LM(lm_model, api_key=api_key)
    dspy.configure(lm=lm)
    return lm


if __name__ == "__main__":
    print("DSPy Prompt Optimizer initialized.")
