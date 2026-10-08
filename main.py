"""Command-line entry point for running a sample Wedding Planner workflow.

Use ``python main.py`` for a CrewAI run, ``--process hierarchical``
to enable manager delegation, or ``--dry-run`` to exercise tools without an API
key. The module prints structured task results and the final coordinator brief.
"""

import argparse
import json
import os
import sys

from dotenv import load_dotenv

import sample_data
from tools import (
    audit_contract_clause,
    extract_payment_milestones,
    recalculate_timeline,
    solve_seating_arrangement,
)


def _banner(title: str) -> None:
    """Print a section heading in the CLI output."""
    print(f"\n{'=' * 78}\n{title}\n{'=' * 78}")


def run_dry() -> None:
    """Exercise the deterministic tools without an LLM (no API key required)."""
    _banner("DRY RUN - Vendor tools: audit_contract_clause")
    print(audit_contract_clause.invoke({
        "contract_text": sample_data.CONTRACT_TEXT, "venue_rules": sample_data.VENUE_RULES,
    }))
    _banner("DRY RUN - Vendor tools: extract_payment_milestones")
    print(extract_payment_milestones.invoke({"contract_text": sample_data.CONTRACT_TEXT}))
    _banner("DRY RUN - Guest tools: solve_seating_arrangement (pre-RSVP guest list)")
    print(solve_seating_arrangement.invoke({
        "guest_data_json": json.dumps(sample_data.BASE_GUEST_LIST),
        "table_capacity": sample_data.TABLE_CAPACITY,
    }))
    _banner(f"DRY RUN - Day-of tools: recalculate_timeline ({sample_data.DELAY_MINUTES}-min caterer delay)")
    print(recalculate_timeline.invoke({
        "current_timeline_json": json.dumps(sample_data.TIMELINE),
        "delay_minutes": sample_data.DELAY_MINUTES,
        "delayed_event_name": sample_data.DELAYED_EVENT,
    }))


def run_crew(process: str, verbose: bool) -> None:
    """Build the selected CrewAI process, run sample inputs, and print its results."""
    from crew import build_crew  # deferred so --dry-run works without CrewAI/OpenAI setup

    crew = build_crew(process, verbose=verbose)  # type: ignore[arg-type]
    _banner(f"Wedding Planner - {sample_data.COUPLE_NAMES} - {process} orchestration")
    result = crew.kickoff(inputs=sample_data.build_inputs())

    for output in result.tasks_output:
        _banner(f"[{output.agent}] {output.name or output.description[:60]}")
        print(output.pydantic.model_dump_json(indent=2) if output.pydantic else output.raw)

    _banner("FINAL MASTER BRIEFING")
    print(result.pydantic.model_dump_json(indent=2) if result.pydantic else result.raw)
    print(f"\nToken usage: {result.token_usage}")


def main(argv: list[str] | None = None) -> int:
    """Parse CLI options and run the crew or the deterministic tool demonstration.

    Returns a process exit code. Missing OpenAI credentials trigger the dry run.
    """
    parser = argparse.ArgumentParser(prog="wedding-planner", description=__doc__)
    parser.add_argument("--process", choices=["sequential", "hierarchical"], default="sequential")
    parser.add_argument("--dry-run", action="store_true", help="Run only the deterministic tools (no LLM calls).")
    parser.add_argument("--quiet", action="store_true", help="Disable CrewAI verbose agent traces.")
    args = parser.parse_args(argv)

    load_dotenv()
    if args.dry_run:
        run_dry()
        return 0
    if not os.getenv("OPENAI_API_KEY"):
        print("OPENAI_API_KEY is not set; falling back to --dry-run.", file=sys.stderr)
        run_dry()
        return 0

    run_crew(args.process, verbose=not args.quiet)
    return 0


if __name__ == "__main__":
    sys.exit(main())
