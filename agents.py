"""CrewAI agent definitions for the Wedding Planner team.

``build_agents`` creates vendor, guest-logistics, and day-of specialists plus a
Master Coordinator. LangChain tools and chat models are adapted to CrewAI's
native types here, keeping that framework boundary out of the tool modules.
"""

from typing import Any

from crewai import Agent
from crewai.tools.base_tool import Tool
from crewai.utilities.llm_utils import create_llm
from langchain_core.tools import BaseTool as LangChainTool

from tools import DAY_OF_TOOLS, GUEST_TOOLS, VENDOR_TOOLS


def _crew_tools(tools: list[LangChainTool]) -> list[Tool]:
    # CrewAI 1.x validates tool types strictly, so LangChain tools are wrapped explicitly.
    return [Tool.from_langchain(t) for t in tools]


def build_agents(llm: Any, *, verbose: bool = True, hierarchical: bool = False) -> dict[str, Agent]:
    """Create the agents, keyed by ``vendor``, ``guest``, ``day_of``, and ``coordinator``.

    ``llm`` may be a LangChain chat model or a CrewAI LLM. Set ``hierarchical``
    when the coordinator will manage and delegate the crew's tasks.
    """
    llm = create_llm(llm)  # maps ChatOpenAI(model, temperature, ...) onto CrewAI's native LLM
    vendor = Agent(
        role="Lead Vendor Negotiator & Contract Auditor",
        goal=(
            "Extract contract restrictions, flag conflicts against venue policies, track payment "
            "milestones and build standardized vendor comparison sheets."
        ),
        backstory=(
            "A seasoned event operations director who has read thousands of hospitality contracts. "
            "You know how noise ordinances, curfews, load-in windows, overtime clauses and deposit "
            "schedules quietly blow up budgets, and you never sign off on a clause you have not "
            "verified with your audit tools."
        ),
        tools=_crew_tools(VENDOR_TOOLS),
        llm=llm,
        allow_delegation=False,
        max_iter=8,
        verbose=verbose,
    )

    guest = Agent(
        role="Guest Logistics & Seating Strategist",
        goal=(
            "Ingest unstructured guest messages, update dietary and allergy tables, parse plus-one "
            "changes and recommend conflict-free table arrangements."
        ),
        backstory=(
            "A highly empathetic hospitality concierge. You read between the lines of every RSVP, "
            "treat allergies as safety issues, protect accessibility needs, and quietly keep "
            "feuding relatives at different tables. You always validate seating with the solver."
        ),
        tools=_crew_tools(GUEST_TOOLS),
        llm=llm,
        allow_delegation=False,
        max_iter=8,
        verbose=verbose,
    )

    day_of = Agent(
        role="Real-Time Timeline Controller",
        goal=(
            "Build the master run-of-show, detect schedule delay cascades, recalculate dependent "
            "time blocks and generate vendor broadcast alerts."
        ),
        backstory=(
            "A veteran stage manager and on-site director. You run incidents calmly, protect hard "
            "landmarks like the ceremony, permitted send-offs and venue curfew, and communicate "
            "changes to every vendor with exact call times."
        ),
        tools=_crew_tools(DAY_OF_TOOLS),
        llm=llm,
        allow_delegation=False,
        max_iter=8,
        verbose=verbose,
    )

    # In hierarchical mode CrewAI injects delegation tools into the manager; it must own no tools itself.
    coordinator = Agent(
        role="Master Wedding Coordinator",
        goal=(
            "Orchestrate the specialist agents, reconcile their outputs and deliver a single, "
            "decision-ready briefing for the couple and the on-site team."
        ),
        backstory=(
            "A principal wedding producer who has run hundreds of high-stakes events. You delegate "
            "precisely, challenge weak evidence, and turn specialist reports into clear priorities, "
            "owners and deadlines."
        ),
        llm=llm,
        allow_delegation=hierarchical,
        verbose=verbose,
    )

    return {"vendor": vendor, "guest": guest, "day_of": day_of, "coordinator": coordinator}
