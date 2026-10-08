"""LangChain tools and parsing helpers for deterministic wedding operations.

The tools audit contract clauses, extract payment terms, seat guests against
constraints, and propagate timeline delays. They return JSON strings so agent
outputs can cite concrete findings; date/time math and seating constraints are
computed in code rather than left to the LLM. Tool input formats are documented
in each decorated function's docstring.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from typing import Any

from langchain_core.tools import tool

# --------------------------------------------------------------------------- #
# Shared parsing helpers
# --------------------------------------------------------------------------- #
_AMPM_RE = re.compile(r"\b(\d{1,2})(?::([0-5]\d))?\s*([ap])\.?\s?m\b\.?", re.IGNORECASE)
_H24_RE = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)\b")
_DB_RE = re.compile(r"(\d{2,3})\s*(?:dBA?|decibels?)\b", re.IGNORECASE)
_SENTENCE_RE = re.compile(r"(?<=[.;!?])\s+|\n+")
_DAY_ROLLOVER = 6 * 60  # clock times before 06:00 belong to the same (late) event night
_MINUTES_PER_DAY = 24 * 60

_MUSIC_WORDS = r"(music|perform\w*|amplified|\bdj\b|\bband\b|entertainment)"
_END_WORDS = r"\b(until|end|ends|cease|conclude|stop|no later than)\b"

_CONTRACT_DIMENSIONS: dict[str, re.Pattern[str]] = {
    "load_in": re.compile(r"load[- ]?in|vendor access|access begins|set[- ]?up|arriv", re.I),
    "music_end": re.compile(rf"{_MUSIC_WORDS}.*{_END_WORDS}|{_END_WORDS}.*{_MUSIC_WORDS}", re.I),
    "curfew": re.compile(r"curfew|vacate|off (?:the )?premises", re.I),
    "noise_limit": re.compile(r"\bdBA?\b|decibel", re.I),
}

_SEVERITY_RANK = {"none": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}


def _normalize_night(minutes: int) -> int:
    """Map early-morning clock times (e.g. 00:30) past midnight of the event day."""
    return minutes + _MINUTES_PER_DAY if minutes < _DAY_ROLLOVER else minutes


def _extract_time(text: str) -> int | None:
    """Return the first clock time in `text` as minutes after midnight."""
    match = _AMPM_RE.search(text)
    if match:
        hour, minute, meridiem = int(match.group(1)) % 12, int(match.group(2) or 0), match.group(3).lower()
        return _normalize_night(hour * 60 + minute + (720 if meridiem == "p" else 0))
    match = _H24_RE.search(text)
    if match:
        return _normalize_night(int(match.group(1)) * 60 + int(match.group(2)))
    return None


def _fmt(minutes: int) -> str:
    return f"{(minutes // 60) % 24:02d}:{minutes % 60:02d}"


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_RE.split(text) if s and s.strip()]


def _scan_terms(text: str) -> dict[str, dict[str, Any]]:
    """Find the first sentence per dimension and pull its numeric value."""
    found: dict[str, dict[str, Any]] = {}
    for sentence in _sentences(text):
        for dim, pattern in _CONTRACT_DIMENSIONS.items():
            if dim in found or not pattern.search(sentence):
                continue
            if dim == "noise_limit":
                db = _DB_RE.search(sentence)
                value = int(db.group(1)) if db else None
            else:
                value = _extract_time(sentence)
            if value is not None:
                found[dim] = {"value": value, "evidence": sentence}
    return found


def _error(message: str, **extra: Any) -> str:
    return json.dumps({"error": message, **extra}, indent=2)


def _as_list(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, str):
        return [value]
    return [str(v) for v in value if str(v).strip()]


# --------------------------------------------------------------------------- #
# Tool 1: contract vs. venue audit
# --------------------------------------------------------------------------- #
@tool
def audit_contract_clause(contract_text: str, venue_rules: str) -> str:
    """Compare a vendor contract against venue policies.

    Checks load-in time vs. venue access, amplified-music end time vs. venue music
    cutoff, overall end time vs. hard curfew, and contracted decibel levels vs.
    venue noise limit. Returns JSON with one finding per dimension
    (status: conflict | compliant | unverified), severity, quoted evidence and a
    recommendation.
    """
    contract, venue = _scan_terms(contract_text), _scan_terms(venue_rules)
    findings: list[dict[str, Any]] = []

    def add(clause: str, status: str, severity: str, contract_value: str, venue_value: str,
            detail: str, recommendation: str) -> None:
        findings.append({
            "clause": clause,
            "status": status,
            "severity": severity,
            "contract_value": contract_value,
            "venue_value": venue_value,
            "detail": detail,
            "recommendation": recommendation,
            "contract_evidence": contract.get(clause, {}).get("evidence", ""),
            "venue_evidence": venue.get(clause, {}).get("evidence", ""),
        })

    # Load-in: vendor must not arrive before the venue opens its doors.
    c_load, v_load = contract.get("load_in"), venue.get("load_in")
    if c_load and v_load:
        early = v_load["value"] - c_load["value"]
        if early > 0:
            add("load_in", "conflict", "high", _fmt(c_load["value"]), _fmt(v_load["value"]),
                f"Vendor plans to load in {early} min before venue access opens.",
                f"Move vendor call time to {_fmt(v_load['value'])} or negotiate a paid early-access window.")
        else:
            add("load_in", "compliant", "none", _fmt(c_load["value"]), _fmt(v_load["value"]),
                "Load-in falls inside the venue access window.", "No action.")
    elif v_load:
        add("load_in", "unverified", "medium", "not stated", _fmt(v_load["value"]),
            "Contract does not specify a load-in time.",
            f"Add a clause fixing load-in no earlier than {_fmt(v_load['value'])}.")

    # Amplified music: contract end vs. venue music cutoff (or curfew if no cutoff exists).
    c_music, v_music, v_curfew = contract.get("music_end"), venue.get("music_end"), venue.get("curfew")
    music_limit = v_music or v_curfew
    if c_music and music_limit:
        overrun = c_music["value"] - music_limit["value"]
        if overrun > 0:
            add("music_end", "conflict", "critical", _fmt(c_music["value"]), _fmt(music_limit["value"]),
                f"Contracted performance runs {overrun} min past the venue's amplified-music cutoff.",
                f"Amend performance end to {_fmt(music_limit['value'])}; reprice or remove the last "
                f"{overrun} min and confirm no overtime is billed for venue-mandated stops.")
        else:
            add("music_end", "compliant", "none", _fmt(c_music["value"]), _fmt(music_limit["value"]),
                "Performance ends within the venue cutoff.", "No action.")
    elif music_limit:
        add("music_end", "unverified", "medium", "not stated", _fmt(music_limit["value"]),
            "Contract does not state when amplified music ends.",
            f"Add an explicit end time no later than {_fmt(music_limit['value'])}.")

    # Hard curfew: the latest contractual commitment must leave load-out buffer before curfew.
    c_end = contract.get("curfew") or c_music
    if v_curfew and c_end:
        buffer = v_curfew["value"] - c_end["value"]
        if buffer < 0:
            add("curfew", "conflict", "critical", _fmt(c_end["value"]), _fmt(v_curfew["value"]),
                f"Contract obligations extend {-buffer} min beyond the hard curfew.",
                "Contract must end before curfew with load-out time included.")
        elif buffer < 30:
            add("curfew", "conflict", "medium", _fmt(c_end["value"]), _fmt(v_curfew["value"]),
                f"Only {buffer} min between contracted end and curfew for load-out.",
                "Require a documented load-out plan or end the service earlier.")
        else:
            add("curfew", "compliant", "none", _fmt(c_end["value"]), _fmt(v_curfew["value"]),
                f"{buffer} min buffer before curfew.", "No action.")

    # Noise: contracted output vs. venue decibel limit.
    c_db, v_db = contract.get("noise_limit"), venue.get("noise_limit")
    if c_db and v_db:
        excess = c_db["value"] - v_db["value"]
        if excess > 0:
            add("noise_limit", "conflict", "high", f"{c_db['value']} dB", f"{v_db['value']} dB",
                f"Contracted output exceeds venue limit by {excess} dB (check measurement point).",
                f"Require an inline sound limiter set to {v_db['value']} dB and a sound check sign-off.")
        else:
            add("noise_limit", "compliant", "none", f"{c_db['value']} dB", f"{v_db['value']} dB",
                "Sound levels within venue limit.", "No action.")
    elif v_db:
        add("noise_limit", "unverified", "medium", "not stated", f"{v_db['value']} dB",
            "Contract does not cap sound output.",
            f"Add a clause capping output at {v_db['value']} dB.")

    conflicts = [f for f in findings if f["status"] == "conflict"]
    highest = max((f["severity"] for f in findings), key=_SEVERITY_RANK.__getitem__, default="none")
    return json.dumps({
        "findings": findings,
        "conflict_count": len(conflicts),
        "highest_severity": highest,
    }, indent=2)


# --------------------------------------------------------------------------- #
# Tool 2 (supporting): payment milestone extraction
# --------------------------------------------------------------------------- #
_MONEY_RE = re.compile(r"\$\s?([\d,]+(?:\.\d{1,2})?)")
_PERCENT_RE = re.compile(r"(\d{1,3}(?:\.\d+)?)\s*%")
_TOTAL_RE = re.compile(
    r"\$\s?([\d,]+(?:\.\d{1,2})?)\s+(?:contract\s+)?total|total\s+(?:fee|price|cost|of)?\s*(?:is\s+)?\$\s?([\d,]+(?:\.\d{1,2})?)",
    re.IGNORECASE,
)
_DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_TRIGGER_RE = re.compile(
    r"upon signing|at signing|on the event date|\d+\s+days\s+(?:before|prior to)\s+the event", re.IGNORECASE
)
_LABEL_RE = re.compile(
    r"final balance|second payment|third payment|deposit|retainer|installment|balance", re.IGNORECASE
)
_FEE_RE = re.compile(r"cancel|overtime|forfeit|surcharge|late fee|per hour|non-refundable", re.IGNORECASE)


def _money(raw: str) -> float:
    return float(raw.replace(",", ""))


@tool
def extract_payment_milestones(contract_text: str, contract_total_usd: float = 0.0) -> str:
    """Extract payment milestones (deposit, installments, final balance) from contract text.

    Percent-based milestones are converted to dollars using contract_total_usd, or the
    total detected in the text when contract_total_usd is 0. Returns JSON with the
    milestones, the scheduled sum vs. contract total, and fee/penalty clauses
    (cancellation, overtime) that affect budget risk.
    """
    total = contract_total_usd
    if not total:
        match = _TOTAL_RE.search(contract_text)
        if match:
            total = _money(match.group(1) or match.group(2))

    milestones: list[dict[str, Any]] = []
    fee_clauses: list[str] = []
    for sentence in _sentences(contract_text):
        if re.search(r"\bdue\b|\bpayable\b", sentence, re.IGNORECASE):
            percent = _PERCENT_RE.search(sentence)
            amounts = [_money(m) for m in _MONEY_RE.findall(sentence)]
            if percent and total:
                amount = round(total * float(percent.group(1)) / 100, 2)
            else:
                amount = next((a for a in amounts if a != total), amounts[0] if amounts else None)
            if amount is None:
                continue
            date, trigger, label = _DATE_RE.search(sentence), _TRIGGER_RE.search(sentence), _LABEL_RE.search(sentence)
            milestones.append({
                "label": label.group(0).lower() if label else "payment",
                "amount_usd": amount,
                "percent_of_total": float(percent.group(1)) if percent else (round(amount / total * 100, 1) if total else None),
                "due": date.group(0) if date else (trigger.group(0) if trigger else "unspecified"),
                "evidence": sentence,
            })
        elif _FEE_RE.search(sentence):
            fee_clauses.append(sentence)

    scheduled = round(sum(m["amount_usd"] for m in milestones), 2)
    return json.dumps({
        "contract_total_usd": total or None,
        "scheduled_total_usd": scheduled,
        "unscheduled_gap_usd": round(total - scheduled, 2) if total else None,
        "milestones": milestones,
        "fee_and_penalty_clauses": fee_clauses,
    }, indent=2)


# --------------------------------------------------------------------------- #
# Tool 3: seating solver
# --------------------------------------------------------------------------- #
_ATTENDING = {"attending", "yes", "accepted", "confirmed", "invited"}


@tool
def solve_seating_arrangement(guest_data_json: str, table_capacity: int) -> str:
    """Allocate attending guests to tables while respecting constraints.

    guest_data_json is a JSON array (or an object with a "guests" array). Each guest:
    name (required), rsvp ("attending" | "declined" | "pending"; default attending),
    party (guests sharing a party id always sit together: couples, plus-ones, caregivers),
    tags (relationship tags, e.g. "bride_family", "college_friends"; shared tags attract),
    avoid (names that must never share a table), dietary (string or list),
    allergies (list), mobility (e.g. "wheelchair"; such guests go to accessible tables).
    Returns JSON with tables, per-table meal counts, allergy alerts, accessibility
    flags, excluded guests and warnings.
    """
    if table_capacity < 1:
        return _error("table_capacity must be >= 1")
    try:
        data = json.loads(guest_data_json)
    except json.JSONDecodeError as exc:
        return _error(f"guest_data_json is not valid JSON: {exc}")
    raw_guests = data.get("guests", []) if isinstance(data, dict) else data
    if not isinstance(raw_guests, list):
        return _error("Expected a JSON array of guests")

    warnings: list[str] = []
    attending: list[dict[str, Any]] = []
    excluded: list[dict[str, str]] = []
    for raw in raw_guests:
        if not isinstance(raw, dict) or not str(raw.get("name", "")).strip():
            warnings.append(f"Skipped malformed guest entry: {raw!r}")
            continue
        guest = {
            "name": str(raw["name"]).strip(),
            "rsvp": str(raw.get("rsvp", "attending")).strip().lower(),
            "party": str(raw.get("party") or "").strip().lower(),
            "tags": {t.lower() for t in _as_list(raw.get("tags"))},
            "avoid": {a.lower() for a in _as_list(raw.get("avoid"))},
            "dietary": _as_list(raw.get("dietary")) or ["standard"],
            "allergies": _as_list(raw.get("allergies")),
            "mobility": str(raw.get("mobility") or "").strip(),
        }
        if guest["rsvp"] in _ATTENDING:
            attending.append(guest)
        else:
            excluded.append({"name": guest["name"], "rsvp": guest["rsvp"]})

    attending_names = {g["name"].lower() for g in attending}
    # Avoid constraints are symmetric even if only one side declared them.
    for guest in attending:
        for other in guest["avoid"]:
            if other not in attending_names:
                continue
            target = next(g for g in attending if g["name"].lower() == other)
            target["avoid"].add(guest["name"].lower())

    # Build indivisible seating units from party ids.
    units_by_party: dict[str, list[dict[str, Any]]] = {}
    for guest in attending:
        key = guest["party"] or f"solo::{guest['name'].lower()}"
        units_by_party.setdefault(key, []).append(guest)
    units: list[list[dict[str, Any]]] = []
    for key, members in units_by_party.items():
        if len(members) > table_capacity:
            warnings.append(f"Party '{key}' has {len(members)} guests (> capacity {table_capacity}); split across tables.")
            units.extend(members[i:i + table_capacity] for i in range(0, len(members), table_capacity))
        else:
            units.append(members)

    # Most constrained first: mobility needs, then avoid lists, then larger parties.
    units.sort(key=lambda u: (
        not any(g["mobility"] for g in u),
        -sum(len(g["avoid"]) for g in u),
        -len(u),
    ))

    def new_table() -> dict[str, Any]:
        return {"guests": [], "names": set(), "avoid": set(), "tags": Counter(), "accessible": False}

    tables = [new_table() for _ in range(max(1, math.ceil(len(attending) / table_capacity)))]
    for unit in units:
        names = {g["name"].lower() for g in unit}
        avoid = set().union(*(g["avoid"] for g in unit))
        tags = set().union(*(g["tags"] for g in unit))
        needs_access = any(g["mobility"] for g in unit)

        best, best_score = None, float("-inf")
        for table in tables:
            if len(table["guests"]) + len(unit) > table_capacity:
                continue
            if names & table["avoid"] or avoid & table["names"]:
                continue
            # Affinity = shared relationship tags; an empty table beats a table of strangers.
            score: float = sum(table["tags"][t] for t in tags) if table["guests"] else 0.5
            if needs_access and table["accessible"]:
                score += 2
            if score > best_score:
                best, best_score = table, score
        if best is None:
            best = new_table()
            tables.append(best)
            warnings.append(f"Opened an extra table to satisfy constraints for: {', '.join(g['name'] for g in unit)}")

        best["guests"].extend(unit)
        best["names"] |= names
        best["avoid"] |= avoid
        best["tags"].update(tags)
        best["accessible"] = best["accessible"] or needs_access

    result_tables = []
    for table in (t for t in tables if t["guests"]):
        number = len(result_tables) + 1
        meals = Counter(d for g in table["guests"] for d in g["dietary"])
        result_tables.append({
            "table_number": number,
            "guests": [g["name"] for g in table["guests"]],
            "seats_open": table_capacity - len(table["guests"]),
            "dominant_tags": [t for t, _ in table["tags"].most_common(2)],
            "meal_counts": dict(meals),
            "allergy_alerts": [f"{g['name']}: {', '.join(g['allergies'])}" for g in table["guests"] if g["allergies"]],
            "accessible": table["accessible"],
            "accessibility_notes": (
                "Place near exit and restrooms; remove one chair and keep a 36in clear aisle. Needs: "
                + "; ".join(f"{g['name']} ({g['mobility']})" for g in table["guests"] if g["mobility"])
            ) if table["accessible"] else "",
        })

    # Independent post-check so the agent can trust the plan.
    seat_of = {name.lower(): t["table_number"] for t in result_tables for name in t["guests"]}
    violations = sorted({
        " / ".join(sorted((g["name"], other)))
        for g in attending for other in g["avoid"]
        if other in seat_of and seat_of[other] == seat_of[g["name"].lower()]
    })
    dietary_summary = Counter(d for g in attending for d in g["dietary"])

    return json.dumps({
        "table_capacity": table_capacity,
        "total_attending": len(attending),
        "tables_used": len(result_tables),
        "tables": result_tables,
        "dietary_summary": dict(dietary_summary),
        "excluded_guests": excluded,
        "avoid_constraint_violations": violations,
        "warnings": warnings,
    }, indent=2)


# --------------------------------------------------------------------------- #
# Tool 4: delay cascade / timeline recalculation
# --------------------------------------------------------------------------- #
def _parse_clock(value: Any) -> int | None:
    return _extract_time(str(value)) if value not in (None, "") else None


@tool
def recalculate_timeline(current_timeline_json: str, delay_minutes: int, delayed_event_name: str) -> str:
    """Propagate a delay through the wedding-day run-of-show.

    current_timeline_json: JSON object with "events" (list) and optional "hard_curfew"
    ("HH:MM"), or a bare list of events. Each event: name, start ("HH:MM", 24h),
    duration_minutes, vendor, fixed (bool; fixed landmarks never move),
    depends_on (names that must finish first), compressible_minutes (max minutes the
    event may be shortened). The delayed event starts delay_minutes late, dependents
    cascade, and any overrun into a fixed landmark or the curfew is absorbed by
    compressing affected events. Returns JSON with the revised timeline, unresolved
    conflicts and vendor alerts.
    """
    if delay_minutes < 0:
        return _error("delay_minutes must be >= 0")
    try:
        data = json.loads(current_timeline_json)
    except json.JSONDecodeError as exc:
        return _error(f"current_timeline_json is not valid JSON: {exc}")
    raw_events = data.get("events", []) if isinstance(data, dict) else data
    curfew = _parse_clock(data.get("hard_curfew")) if isinstance(data, dict) else None

    events: dict[str, dict[str, Any]] = {}
    warnings: list[str] = []
    for raw in raw_events:
        try:
            start = _parse_clock(raw["start"])
            if start is None:
                raise ValueError(f"unreadable start '{raw['start']}'")
            event = {
                "name": str(raw["name"]).strip(),
                "vendor": str(raw.get("vendor", "Planner")),
                "start": start,
                "duration": int(raw["duration_minutes"]),
                "fixed": bool(raw.get("fixed", False)),
                "depends_on": [str(d).strip().lower() for d in raw.get("depends_on", [])],
                "compressible": max(0, int(raw.get("compressible_minutes", 0))),
            }
        except (KeyError, TypeError, ValueError) as exc:
            return _error(f"Invalid event {raw!r}: {exc}")
        key = event["name"].lower()
        if key in events:
            return _error(f"Duplicate event name: {event['name']}")
        events[key] = event

    target = delayed_event_name.strip().lower()
    if target not in events:
        return _error(f"Event '{delayed_event_name}' not found", available_events=[e["name"] for e in events.values()])
    if events[target]["fixed"]:
        warnings.append(f"'{events[target]['name']}' is a fixed landmark; delaying it moves a landmark.")

    for event in events.values():
        unknown = [d for d in event["depends_on"] if d not in events]
        if unknown:
            warnings.append(f"'{event['name']}' depends on unknown events {unknown}; ignored.")
            event["depends_on"] = [d for d in event["depends_on"] if d in events]

    order = sorted(events, key=lambda k: events[k]["start"])
    position = {k: i for i, k in enumerate(order)}
    duration = {k: events[k]["duration"] for k in events}
    compressed = {k: 0 for k in events}

    # Everything downstream of the delayed event is "affected" and eligible for compression.
    affected = {target}
    for key in order:
        if any(d in affected for d in events[key]["depends_on"]) and not events[key]["fixed"]:
            affected.add(key)

    def schedule() -> dict[str, tuple[int, int]]:
        plan: dict[str, tuple[int, int]] = {}
        for key in order:
            event = events[key]
            start = event["start"] + (delay_minutes if key == target else 0)
            if not event["fixed"]:
                for dep in event["depends_on"]:
                    if dep in plan:  # dependencies listed later in the day are ignored
                        start = max(start, plan[dep][1])
            plan[key] = (start, start + duration[key])
        return plan

    def ancestors(key: str) -> set[str]:
        seen, stack = set(), list(events[key]["depends_on"])
        while stack:
            dep = stack.pop()
            if dep not in seen:
                seen.add(dep)
                stack.extend(events[dep]["depends_on"])
        return seen

    def violations(plan: dict[str, tuple[int, int]]) -> list[tuple[str, int, str]]:
        found = []
        for key, event in events.items():
            if event["fixed"] and key != target:
                for dep in event["depends_on"]:
                    overrun = plan[dep][1] - plan[key][0]
                    if overrun > 0:
                        found.append((dep, overrun, f"overruns fixed landmark '{event['name']}'"))
        if curfew is not None:
            for key, event in events.items():
                overrun = plan[key][1] - curfew
                if overrun > 0 and not event["fixed"]:
                    found.append((key, overrun, f"runs past hard curfew {_fmt(curfew)}"))
        return sorted(found, key=lambda v: -v[1])

    unresolved: dict[tuple[str, str], int] = {}
    for _ in range(10 * len(events) + 10):
        plan = schedule()
        open_violations = [v for v in violations(plan) if (v[0], v[2]) not in unresolved]
        if not open_violations:
            break
        culprit, overrun, reason = open_violations[0]
        # Shorten the latest affected, compressible event on the culprit's critical chain first.
        chain = sorted(({culprit} | ancestors(culprit)) & affected, key=lambda k: -position[k])
        candidate = next((k for k in chain if not events[k]["fixed"]
                          and compressed[k] < events[k]["compressible"]), None)
        if candidate is None:
            unresolved[(culprit, reason)] = overrun
            continue
        cut = min(overrun, events[candidate]["compressible"] - compressed[candidate])
        duration[candidate] -= cut
        compressed[candidate] += cut

    plan = schedule()
    remaining = {(v[0], v[2]): v[1] for v in violations(plan)}
    conflict_keys = {k[0] for k in remaining}

    revised, alerts_by_vendor = [], {}
    for key in order:
        event, (new_start, new_end) = events[key], plan[key]
        shift = new_start - event["start"]
        if key in conflict_keys:
            status = "conflict"
        elif event["fixed"]:
            status = "fixed"
        elif compressed[key]:
            status = "compressed"
        elif shift:
            status = "shifted"
        else:
            status = "on_time"
        revised.append({
            "name": event["name"],
            "vendor": event["vendor"],
            "fixed": event["fixed"],
            "original_start": _fmt(event["start"]),
            "original_end": _fmt(event["start"] + event["duration"]),
            "new_start": _fmt(new_start),
            "new_end": _fmt(new_end),
            "shift_minutes": shift,
            "compressed_by_minutes": compressed[key],
            "status": status,
        })
        if shift or compressed[key]:
            note = f"{event['name']}: {_fmt(event['start'])} -> {_fmt(new_start)} (ends {_fmt(new_end)})"
            if compressed[key]:
                note += f", shortened by {compressed[key]} min"
            alerts_by_vendor.setdefault(event["vendor"], []).append(note)

    alerts = [
        {
            "recipient": vendor,
            "priority": "urgent" if any("shortened" in n for n in notes) else "high",
            "message": "SCHEDULE CHANGE - " + "; ".join(notes),
        }
        for vendor, notes in alerts_by_vendor.items()
    ]
    alerts.append({
        "recipient": "ALL VENDORS",
        "priority": "high",
        "message": (
            f"'{events[target]['name']}' delayed {delay_minutes} min. "
            f"Fixed landmarks unchanged: {', '.join(e['name'] for e in events.values() if e['fixed']) or 'none'}. "
            + (f"Hard curfew {_fmt(curfew)} holds." if curfew is not None else "")
        ).strip(),
    })

    last_end = max(end for _, end in plan.values())
    return json.dumps({
        "delayed_event": events[target]["name"],
        "delay_minutes": delay_minutes,
        "hard_curfew": _fmt(curfew) if curfew is not None else None,
        "curfew_safe": curfew is None or last_end <= curfew,
        "total_minutes_compressed": sum(compressed.values()),
        "revised_timeline": revised,
        "unresolved_conflicts": [
            {"event": events[k[0]]["name"], "issue": k[1], "overrun_minutes": m} for k, m in remaining.items()
        ],
        "vendor_alerts": alerts,
        "warnings": warnings,
    }, indent=2)


VENDOR_TOOLS = [audit_contract_clause, extract_payment_milestones]
GUEST_TOOLS = [solve_seating_arrangement]
DAY_OF_TOOLS = [recalculate_timeline]
