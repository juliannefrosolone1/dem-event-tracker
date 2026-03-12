import anthropic
import json
import os
import time
from datetime import datetime, date, timedelta
from pathlib import Path

EVENTS_FILE = Path(__file__).parent.parent / "public" / "events.json"

CANDIDATES = [
    {"id": "aoc",        "name": "Alexandria Ocasio-Cortez"},
    {"id": "newsom",     "name": "Gavin Newsom"},
    {"id": "harris",     "name": "Kamala Harris"},
    {"id": "pritzker",   "name": "J.B. Pritzker"},
    {"id": "kelly",      "name": "Mark Kelly"},
    {"id": "booker",     "name": "Cory Booker"},
    {"id": "shapiro",    "name": "Josh Shapiro"},
    {"id": "khanna",     "name": "Ro Khanna"},
    {"id": "crow",       "name": "Jason Crow"},
    {"id": "slotkin",    "name": "Elissa Slotkin"},
    {"id": "murphy",     "name": "Chris Murphy"},
    {"id": "buttigieg",  "name": "Pete Buttigieg"},
    {"id": "ossoff",     "name": "Jon Ossoff"},
]

SYSTEM_PROMPT = """You are a political intelligence analyst tracking potential 2028 Democratic
presidential primary candidates. Your job is to find recent public events, speeches, rallies,
town halls, fundraisers, TV/media appearances, and significant press coverage for these candidates.

Return ONLY a valid JSON array. No preamble, no markdown, no backticks. Just raw JSON.

Each event object must have exactly these fields:
{
  "id": "unique string like candidate_id-YYYY-MM-DD-slug",
  "candidate": "candidate id string",
  "date": "YYYY-MM-DD",
  "event_type": one of ["rally", "town_hall", "speech", "fundraiser", "interview", "media_appearance", "endorsement", "travel", "other"],
  "title": "short descriptive title",
  "location_city": "city name or empty string",
  "location_state": "2-letter state code or empty string",
  "location_display": "City, ST or 'Virtual' or 'National'",
  "venue": "venue name or empty string",
  "description": "1-2 sentence description of the event",
  "significance": one of ["high", "medium", "low"],
  "press_clips": [
    {
      "outlet": "news outlet name",
      "headline": "article headline",
      "url": "full url if known, empty string if not",
      "date": "YYYY-MM-DD"
    }
  ]
}

Only include events you are confident actually occurred. Return an empty array [] if you find nothing new.
Track events in ALL 50 states, not just early primary states. Include any state where the candidate
appeared publicly."""

def load_existing_events():
    if EVENTS_FILE.exists():
        with open(EVENTS_FILE) as f:
            return json.load(f)
    return {"events": [], "last_updated": "", "meta": {"source": "auto-fetched via Anthropic API + web search"}}

def save_events(data):
    data["last_updated"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(EVENTS_FILE, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Saved {len(data['events'])} total events to {EVENTS_FILE}")

def existing_ids(data):
    return {e["id"] for e in data["events"]}

def fetch_events_for_candidate(client, candidate, lookback_days=440):
    since_date = max(
        (date.today() - timedelta(days=lookback_days)).strftime("%Y-%m-%d"),
        "2025-01-01"
    )
    today = date.today().strftime("%Y-%m-%d")

    prompt = f"""Search the web for public events, appearances, speeches, media appearances, and press coverage
for {candidate['name']} between {since_date} and {today}.

Look for:
- Public rallies, town halls, or campaign-style events in ANY state
- Major speeches (Senate floor, think tanks, conferences, universities)
- TV interviews and podcast appearances
- Travel to any US state, with special attention to early primary states (Iowa, New Hampshire, Nevada, South Carolina, Georgia)
- Fundraising events
- Endorsements given or received
- Significant op-eds or public statements covered by national media

Return a JSON array of event objects as specified. Include press clip URLs when available.
For {candidate['name']}, use candidate id: "{candidate['id']}" """

    try:
        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=2000,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}]
        )

        full_text = ""
        for block in response.content:
            if hasattr(block, "text"):
                full_text += block.text

        full_text = full_text.strip()
        if full_text.startswith("```"):
