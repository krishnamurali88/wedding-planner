"""Validated Pydantic contracts for specialist task results and final synthesis.

CrewAI tasks use these models through ``output_pydantic``. The schemas describe
vendor conflicts and payments, guest records and seating, revised timelines,
and the coordinator's action-oriented briefing. Avoiding generic dict fields
keeps the output contracts suitable for structured LLM responses.
"""

from typing import Literal

from pydantic import BaseModel, Field

Severity = Literal["low", "medium", "high", "critical"]


# --------------------------------------------------------------------------- #
# Task 1 - Vendor Coordinator
# --------------------------------------------------------------------------- #
class ContractConflict(BaseModel):
    clause: str = Field(description="Contract dimension, e.g. load_in, music_end, curfew, noise_limit")
    contract_term: str = Field(description="What the vendor contract commits to")
    venue_policy: str = Field(description="What the venue allows")
    severity: Severity
    recommendation: str = Field(description="Concrete renegotiation or mitigation step")


class PaymentMilestone(BaseModel):
    vendor: str
    label: str = Field(description="deposit, second payment, final balance, ...")
    amount_usd: float = Field(ge=0)
    due: str = Field(description="ISO date or trigger such as 'upon signing'")
    status: Literal["paid", "upcoming", "overdue", "unknown"] = "upcoming"


class VendorComparisonRow(BaseModel):
    vendor: str
    category: str
    total_cost_usd: float = Field(ge=0)
    deposit_percent: float = Field(ge=0, le=100)
    cancellation_terms: str
    overtime_rate: str
    compliance_risk: Literal["low", "medium", "high"]
    notes: str


class VendorAuditReport(BaseModel):
    conflicts: list[ContractConflict]
    payment_milestones: list[PaymentMilestone]
    comparison_sheet: list[VendorComparisonRow]
    required_contract_amendments: list[str]
    summary: str


# --------------------------------------------------------------------------- #
# Task 2 - Guest Experience & RSVP
# --------------------------------------------------------------------------- #
class GuestRecord(BaseModel):
    name: str
    rsvp: Literal["attending", "declined", "pending"]
    party: str = Field(description="Shared id for guests who must sit together (couples, plus-ones, caregivers)")
    dietary: list[str]
    allergies: list[str]
    mobility: str = Field(description="Accessibility need, or empty string")
    avoid: list[str] = Field(description="Guests who must not share a table with this guest")
    change_note: str = Field(description="What changed and which RSVP message it came from, or 'unchanged'")


class DietaryCount(BaseModel):
    requirement: str
    count: int = Field(ge=0)


class TableAssignment(BaseModel):
    table_number: int = Field(ge=1)
    guests: list[str]
    meal_notes: str
    accessibility_notes: str


class GuestLogisticsReport(BaseModel):
    guests: list[GuestRecord]
    dietary_summary: list[DietaryCount]
    allergy_alerts: list[str]
    plus_one_changes: list[str]
    seating_plan: list[TableAssignment]
    open_questions: list[str]


# --------------------------------------------------------------------------- #
# Task 3 - Day-Of Execution
# --------------------------------------------------------------------------- #
class TimelineBlock(BaseModel):
    name: str
    vendor: str
    start: str = Field(description="HH:MM, 24h")
    end: str = Field(description="HH:MM, 24h")
    status: Literal["on_time", "shifted", "compressed", "fixed", "conflict"]
    change_note: str


class VendorAlert(BaseModel):
    recipient: str
    priority: Literal["normal", "high", "urgent"]
    message: str


class RunOfShow(BaseModel):
    incident_summary: str
    revised_timeline: list[TimelineBlock]
    landmarks_preserved: list[str]
    curfew_safe: bool
    vendor_alerts: list[VendorAlert]
    contingency_actions: list[str]


# --------------------------------------------------------------------------- #
# Task 4 - Master Coordinator synthesis
# --------------------------------------------------------------------------- #
class ActionItem(BaseModel):
    owner: str
    action: str
    deadline: str


class MasterBriefing(BaseModel):
    executive_summary: str
    readiness: Literal["green", "amber", "red"]
    critical_actions: list[ActionItem]
    open_risks: list[str]
    couple_message: str = Field(description="Calm, non-technical update for the couple")
