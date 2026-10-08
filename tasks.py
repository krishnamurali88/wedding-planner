"""CrewAI task prompts and structured output contracts.

``build_tasks`` wires the vendor audit, RSVP/seating, run-of-show, and final
briefing tasks to the agents and Pydantic schemas. Template placeholders are
resolved from the mapping passed to ``Crew.kickoff(inputs=...)``.
"""

from crewai import Agent, Task

from schemas import GuestLogisticsReport, MasterBriefing, RunOfShow, VendorAuditReport


def build_tasks(agents: dict[str, Agent], *, hierarchical: bool = False) -> list[Task]:
    """Create the ordered tasks and connect specialist outputs as task context.

    Pass the mapping returned by ``build_agents``. In hierarchical mode the
    manager owns the final synthesis task, so it is left without an assigned agent.
    """
    vendor_task = Task(
        name="vendor_contract_verification",
        description=(
            "Verify vendor contracts for the wedding of {couple_names} on {wedding_date}.\n\n"
            "Couple preferences:\n{couple_preferences}\n\n"
            "Primary vendor contract:\n{contract_text}\n\n"
            "Venue policies:\n{venue_rules}\n\n"
            "Alternative vendor quotes under consideration:\n{vendor_shortlist}\n\n"
            "Steps:\n"
            "1. Call audit_contract_clause with the full contract text and the venue policies to "
            "compare load-in timing, amplified-music end time, curfew and decibel limits.\n"
            "2. Call extract_payment_milestones on the contract and verify the milestones add up "
            "to the contract total. Mark milestones whose due date is before {today} as overdue "
            "unless stated paid.\n"
            "3. Report every conflict with a severity and a concrete renegotiation or mitigation.\n"
            "4. Build one standardized comparison row per vendor (contracted and shortlisted), "
            "rating compliance risk against the venue policies and couple preferences.\n"
            "Only report facts supported by tool output or the provided text."
        ),
        expected_output=(
            "A VendorAuditReport: contract conflicts with severity, payment milestones, a vendor "
            "comparison sheet, required contract amendments and a short summary."
        ),
        agent=agents["vendor"],
        output_pydantic=VendorAuditReport,
    )

    guest_task = Task(
        name="rsvp_processing_and_seating",
        description=(
            "Process incoming RSVP messages for {couple_names}.\n\n"
            "Current guest list (JSON):\n{base_guest_list}\n\n"
            "Raw RSVP messages:\n{rsvp_messages}\n\n"
            "Steps:\n"
            "1. Parse each message for attendance, plus-one additions or removals, dietary needs, "
            "allergies (treat as safety-critical), mobility needs and 'do not seat near' requests. "
            "Map nicknames such as 'Uncle Raj' to the matching guest-list entry using the notes field.\n"
            "2. Build the updated guest list as a JSON array whose objects use exactly these keys: "
            "name, rsvp, party, tags, avoid, dietary, allergies, mobility. New plus-ones and "
            "caregivers share the host's party id and tags. Removed plus-ones are marked declined.\n"
            "3. Call solve_seating_arrangement with that JSON and table_capacity={table_capacity}. "
            "If it returns warnings or avoid-constraint violations, fix the data and run it again.\n"
            "4. Report the final guest records, dietary counts, caterer allergy alerts, plus-one "
            "changes, the seating plan exactly as returned by the solver, and open questions."
        ),
        expected_output=(
            "A GuestLogisticsReport with updated guest records, dietary summary, allergy alerts, "
            "plus-one changes, a solver-validated seating plan and open questions."
        ),
        agent=agents["guest"],
        output_pydantic=GuestLogisticsReport,
    )

    day_of_task = Task(
        name="day_of_contingency_run_of_show",
        description=(
            "Own the run-of-show for {wedding_date} at {venue_name}.\n\n"
            "Baseline timeline (JSON):\n{timeline_json}\n\n"
            "LIVE INCIDENT: {incident_report}\n\n"
            "Steps:\n"
            "1. Call recalculate_timeline with the baseline JSON, delay_minutes={delay_minutes} "
            "and delayed_event_name='{delayed_event}'.\n"
            "2. Confirm fixed landmarks did not move and explain every compressed block.\n"
            "3. Cross-check against the vendor audit (amplified-music cutoff, curfew, noise) and "
            "guest logistics (allergy alerts, accessible tables) from the previous tasks.\n"
            "4. Write vendor broadcast alerts (one per affected vendor plus an all-vendor broadcast) "
            "with exact new call times, and list contingency actions that protect the guest "
            "experience during the gap."
        ),
        expected_output=(
            "A RunOfShow with incident summary, the revised timeline, preserved landmarks, "
            "curfew safety flag, vendor alerts and contingency actions."
        ),
        agent=agents["day_of"],
        context=[vendor_task, guest_task],
        output_pydantic=RunOfShow,
    )

    synthesis_task = Task(
        name="master_coordinator_briefing",
        description=(
            "Reconcile the vendor audit, guest logistics and day-of run-of-show for "
            "{couple_names}. Identify cross-cutting risks (for example a contracted music end time "
            "that conflicts with the revised timeline, or allergy alerts the caterer must receive "
            "during the delay). Assign every critical action to an owner with a deadline, rate "
            "overall readiness green, amber or red, and write a short reassuring update for the couple."
        ),
        expected_output="A MasterBriefing with summary, readiness, owned actions, open risks and a couple message.",
        # In hierarchical mode the manager agent runs this itself; CrewAI forbids assigning the manager.
        agent=None if hierarchical else agents["coordinator"],
        context=[vendor_task, guest_task, day_of_task],
        output_pydantic=MasterBriefing,
    )

    return [vendor_task, guest_task, day_of_task, synthesis_task]
