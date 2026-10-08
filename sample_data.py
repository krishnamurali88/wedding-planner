"""Editable sample wedding scenario used by the CLI demonstration.

This module supplies couple preferences, vendor and venue text, a guest list and
raw RSVP messages, plus a run-of-show with a 40-minute catering delay. Change
these constants to customize the example; ``build_inputs`` formats them for
CrewAI task interpolation.
"""

import json
from datetime import date

COUPLE_NAMES = "Ava Whitfield & Rohan Patel"
WEDDING_DATE = "2026-10-24"
VENUE_NAME = "Willow Creek Estate"

COUPLE_PREFERENCES = """\
- Budget ceiling: $48,000 total; entertainment budget $6,500.
- Non-negotiables: first dance and toasts stay intact; sparkler send-off at 22:30 (fire-permit window).
- Preferences: a long dance block, eco-conscious vendors, no surprise overtime charges.
- Grandma Eleanor's comfort is the top guest priority."""

CONTRACT_TEXT = """\
SOUNDWAVE ENTERTAINMENT - PERFORMANCE AGREEMENT (DJ + MC services)
Vendor will load in at 2:00 PM on the event date.
Performance shall continue until 11:00 PM.
Sound system output may reach 95 dB at the dance floor.
A 30% deposit of the $6,500 total is due upon signing on 2026-03-01.
The deposit was received on 2026-03-02.
A second payment of 50% is due on 2026-09-15.
The final balance of $1,300 is due on the event date 2026-10-24.
Cancellation within 60 days of the event forfeits all deposits.
Overtime is billed at $350 per hour, in 30-minute increments."""

VENUE_RULES = """\
WILLOW CREEK ESTATE - VENDOR POLICIES
Vendor access begins at 3:00 PM; no early load-in without written approval.
Amplified music must end by 10:30 PM per county ordinance.
Sound levels must not exceed 85 dB measured at the property line.
Curfew: all guests and vendors must vacate by 11:30 PM."""

VENDOR_SHORTLIST = """\
BeatBox Collective (DJ): $5,900 total, 25% deposit, music until 10:30 PM, built-in 85 dB limiter,
50% refund on cancellation until 90 days out, overtime $275/hour, uses LED low-power rig."""

BASE_GUEST_LIST = [
    {"name": "Eleanor Whitfield", "party": "whitfield_e", "tags": ["bride_family", "elders"], "notes": "Bride's grandmother ('Grandma Eleanor')"},
    {"name": "Susan Whitfield", "party": "whitfield_s", "tags": ["bride_family"], "notes": "Bride's aunt, Eleanor's daughter"},
    {"name": "Daniel Wright", "party": "wright", "tags": ["bride_family"]},
    {"name": "Sofia Wright", "party": "wright", "tags": ["bride_family"]},
    {"name": "Raj Patel", "party": "raj", "tags": ["groom_family", "elders"], "notes": "Groom's uncle ('Uncle Raj')"},
    {"name": "Henry Okafor", "party": "okafor", "tags": ["groom_family"]},
    {"name": "Priya Sharma", "party": "sharma", "tags": ["groom_family"]},
    {"name": "Arjun Sharma", "party": "sharma", "tags": ["groom_family"]},
    {"name": "Marcus Lee", "party": "lee", "tags": ["college_friends"]},
    {"name": "Dana Cole", "party": "lee", "tags": ["college_friends"], "notes": "Marcus's plus-one"},
    {"name": "Tom Becker", "party": "becker", "tags": ["college_friends"], "notes": "Allowed a plus-one"},
    {"name": "Grace Kim", "party": "kim", "tags": ["college_friends"]},
    {"name": "Leo Brandt", "party": "brandt", "tags": ["college_friends"]},
    {"name": "Chloe Martin", "party": "martin", "tags": ["work_friends"]},
    {"name": "Ben Martin", "party": "martin", "tags": ["work_friends"]},
    {"name": "Nina Alvarez", "party": "alvarez", "tags": ["work_friends"]},
    {"name": "Omar Haddad", "party": "alvarez", "tags": ["work_friends"]},
    {"name": "Isabel Ruiz", "party": "ruiz", "tags": ["work_friends"], "dietary": ["pescatarian"]},
]

RSVP_MESSAGES = """\
[Priya Sharma] We're thrilled! Arjun and I will both be there. Arjun has a severe tree-nut allergy (EpiPen) and I'm vegetarian. Please, please don't seat us near Uncle Raj - long story.
[Marcus Lee] Sorry, Dana can't make it after all, so it's just me. Also I've gone vegan this year!
[Susan Whitfield, on behalf of Grandma Eleanor] Mom is coming but uses a wheelchair now and needs to be near an exit and the restroom. I'll sit with her to help.
[Tom Becker] Count me in + I'm bringing my girlfriend, Lena Fischer. She has celiac disease so strictly gluten-free.
[Raj Patel] Will attend. No special requests.
[Chloe Martin] Unfortunately Ben and I have to decline - family emergency. Sending love!"""

TIMELINE = {
    "hard_curfew": "23:30",
    "events": [
        {"name": "Vendor load-in & setup", "start": "15:00", "duration_minutes": 90, "vendor": "All Vendors"},
        {"name": "Ceremony", "start": "16:30", "duration_minutes": 30, "vendor": "Officiant", "fixed": True,
         "depends_on": ["Vendor load-in & setup"]},
        {"name": "Cocktail hour", "start": "17:00", "duration_minutes": 60, "vendor": "Bar - Copper Still",
         "depends_on": ["Ceremony"], "compressible_minutes": 15},
        {"name": "Grand entrance", "start": "18:00", "duration_minutes": 10, "vendor": "Soundwave DJ",
         "depends_on": ["Cocktail hour"]},
        {"name": "Dinner service", "start": "18:10", "duration_minutes": 75, "vendor": "Harvest & Vine Catering",
         "depends_on": ["Grand entrance"], "compressible_minutes": 15},
        {"name": "Toasts", "start": "19:25", "duration_minutes": 20, "vendor": "Soundwave DJ",
         "depends_on": ["Dinner service"], "compressible_minutes": 5},
        {"name": "First dance", "start": "19:45", "duration_minutes": 10, "vendor": "Soundwave DJ",
         "depends_on": ["Toasts"]},
        {"name": "Cake cutting", "start": "19:55", "duration_minutes": 15, "vendor": "Sugar Bloom Bakery",
         "depends_on": ["First dance"], "compressible_minutes": 5},
        {"name": "Open dancing", "start": "20:10", "duration_minutes": 140, "vendor": "Soundwave DJ",
         "depends_on": ["Cake cutting"], "compressible_minutes": 60},
        {"name": "Sparkler send-off", "start": "22:30", "duration_minutes": 15, "vendor": "Venue Coordinator",
         "fixed": True, "depends_on": ["Open dancing"]},
        {"name": "Vendor load-out", "start": "22:45", "duration_minutes": 45, "vendor": "All Vendors",
         "depends_on": ["Sparkler send-off"], "compressible_minutes": 10},
    ],
}

DELAYED_EVENT = "Dinner service"
DELAY_MINUTES = 40
INCIDENT_REPORT = (
    "17:45 - Harvest & Vine Catering reports their refrigerated truck broke down on Route 9; a "
    "replacement is en route. Dinner service will start 40 minutes late."
)
TABLE_CAPACITY = 8


def build_inputs() -> dict[str, str | int]:
    """Return sample values keyed to the placeholders in ``tasks.py``."""
    return {
        "couple_names": COUPLE_NAMES,
        "wedding_date": WEDDING_DATE,
        "venue_name": VENUE_NAME,
        "today": date.today().isoformat(),
        "couple_preferences": COUPLE_PREFERENCES,
        "contract_text": CONTRACT_TEXT,
        "venue_rules": VENUE_RULES,
        "vendor_shortlist": VENDOR_SHORTLIST,
        "base_guest_list": json.dumps(BASE_GUEST_LIST, indent=2),
        "rsvp_messages": RSVP_MESSAGES,
        "table_capacity": TABLE_CAPACITY,
        "timeline_json": json.dumps(TIMELINE, indent=2),
        "delay_minutes": DELAY_MINUTES,
        "delayed_event": DELAYED_EVENT,
        "incident_report": INCIDENT_REPORT,
    }
