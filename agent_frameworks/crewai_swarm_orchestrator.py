"""
========================================================================================
CREWAI MULTI-AGENT SWARM ORCHESTRATOR
========================================================================================
Enables hierarchical team delegation:
- Manager / Architect Agent (Plans & distributes work)
- Worker / Specialist Agent (Executes scripts, APIs, tools)
- QA / Critic Agent (Audits output against strict rules)
========================================================================================
"""

import sys
from pathlib import Path
from typing import List, Dict, Any, Optional

# Add crewAI repo to sys.path if needed
CREWAI_REPO = Path(__file__).resolve().parent / "crewAI"
if str(CREWAI_REPO) not in sys.path and CREWAI_REPO.exists():
    sys.path.insert(0, str(CREWAI_REPO))

try:
    from crewai import Agent, Crew, Process, Task
    CREWAI_AVAILABLE = True
except ImportError:
    CREWAI_AVAILABLE = False


class AgentSwarmHub:
    """
    Standard factory for deploying specialized multi-agent teams.
    """

    @staticmethod
    def create_automation_team(
        goal: str,
        llm: Optional[Any] = None,
        tools: Optional[List[Any]] = None,
    ) -> Any:
        if not CREWAI_AVAILABLE:
            raise ImportError("crewAI is not installed. Install via: pip install crewai")

        active_tools = tools or []

        # 1. Lead Architect Agent
        architect = Agent(
            role="Lead System Architect",
            goal=f"Deconstruct the master goal: '{goal}' into flawless, executable engineering tasks.",
            backstory="You are a principal software architect who ensures zero hallucination, strict schema conformance, and clean system design.",
            verbose=True,
            allow_delegation=True,
            llm=llm,
        )

        # 2. Automation Specialist Agent
        engineer = Agent(
            role="Automation Execution Engineer",
            goal="Write, run, and hot-patch production scripts with zero human intervention.",
            backstory="You are an elite developer skilled in Python, Playwright, APIs, and CLI tooling. You execute tasks with zero latency.",
            tools=active_tools,
            verbose=True,
            allow_delegation=False,
            llm=llm,
        )

        # 3. Quality & Security Auditor Agent
        auditor = Agent(
            role="QA & Compliance Officer",
            goal="Verify all outputs, validate schemas, ensure accurate numbers, and enforce Master Directives.",
            backstory="You are an uncompromising auditor. You catch every bug, edge-case, and schema discrepancy.",
            verbose=True,
            allow_delegation=False,
            llm=llm,
        )

        # Build Tasks
        t1 = Task(
            description=f"Formulate complete execution plan for: {goal}",
            expected_output="Step-by-step technical plan with input/output contracts.",
            agent=architect,
        )

        t2 = Task(
            description="Implement and execute the planned automation steps.",
            expected_output="Verified execution output, generated files, or API response.",
            agent=engineer,
        )

        t3 = Task(
            description="Audit the execution output. Confirm zero errors and complete task fulfillment.",
            expected_output="Final audit report verifying task success.",
            agent=auditor,
        )

        crew = Crew(
            agents=[architect, engineer, auditor],
            tasks=[t1, t2, t3],
            process=Process.sequential,
            verbose=True,
        )

        return crew


if __name__ == "__main__":
    print("CrewAI Agent Swarm Hub initialized.")
