"""Construct CrewAI crews and configure their language model.

Sequential mode runs the three specialists before a coordinator synthesis task.
Hierarchical mode installs the Master Coordinator as the CrewAI manager, which
delegates tasks to the specialists. ``build_crew`` returns a configured, not-yet-run Crew.
"""

import os
from typing import Literal

from crewai import Crew, Process
from langchain_openai import ChatOpenAI

from agents import build_agents
from tasks import build_tasks

ProcessMode = Literal["sequential", "hierarchical"]


def build_llm() -> ChatOpenAI:
    """Create the OpenAI chat model from ``WEDDING_PLANNER_MODEL`` (default ``gpt-4o``)."""
    return ChatOpenAI(model=os.getenv("WEDDING_PLANNER_MODEL", "gpt-4o"), temperature=0.2)


def build_crew(process: ProcessMode = "sequential", *, verbose: bool = True) -> Crew:
    """Build a sequential or manager-led crew, ready for ``Crew.kickoff``.

    Args:
        process: ``sequential`` or ``hierarchical`` orchestration mode.
        verbose: Whether CrewAI should emit its agent execution trace.
    """
    hierarchical = process == "hierarchical"
    agents = build_agents(build_llm(), verbose=verbose, hierarchical=hierarchical)
    tasks = build_tasks(agents, hierarchical=hierarchical)
    specialists = [agents["vendor"], agents["guest"], agents["day_of"]]

    if hierarchical:
        # The coordinator becomes the manager and delegates each task to a specialist.
        return Crew(
            agents=specialists,
            tasks=tasks,
            process=Process.hierarchical,
            manager_agent=agents["coordinator"],
            verbose=verbose,
        )
    # Sequential: specialists run in order, then the coordinator synthesizes all outputs.
    return Crew(
        agents=[*specialists, agents["coordinator"]],
        tasks=tasks,
        process=Process.sequential,
        verbose=verbose,
    )
