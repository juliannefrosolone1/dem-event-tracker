"""
fetch_events.py
---------------
Runs daily via GitHub Actions. Uses the Anthropic API (with web search)
to find public events, appearances, and press clips for 2028 Democratic
presidential primary contenders, and merges them into public/events.json.
"""

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
Focus on events that suggest presidential positioning, travel to early states (Iowa, New Hampshire,
Nevada, South Carolina, Georgia), or national media activity."""

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

def fetch_events_for_candidate(client, candidate, lookback_days=14):
    since_date = (date.today() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    today = date.today().strftime("%Y-%m-%d")

    prompt = f"""Search the web for public events, appearances, speeches, media appearances, and press coverage
for {candidate['name']} between {since_date} and {today}.

Look for:
- Public rallies, town halls, or campaign-style events
- Major speeches (Senate floor, think tanks, conferences)
- TV interviews and podcast appearances
- Travel to early primary states (Iowa, New Hampshire, Nevada, South Carolina, Georgia, Michigan, Wisconsin, Pennsylvania)
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

        # Extract text from response
        full_text = ""
        for block in response.content:
            if hasattr(block, "text"):
                full_text += block.text

        # Clean and parse JSON
        full_text = full_text.strip()
        # Strip markdown fences if present
        if full_text.startswith("```"):
            full_text = full_text.split("```")[1]
            if full_text.startswith("json"):
                full_text = full_text[4:]
        full_text = full_text.strip()

        if not full_text or full_text == "[]":
            print(f"  No events found for {candidate['name']}")
            return []

        events = json.loads(full_text)
        if not isinstance(events, list):
            print(f"  Unexpected response format for {candidate['name']}")
            return []

        print(f"  Found {len(events)} events for {candidate['name']}")
        return events

    except json.JSONDecodeError as e:
        print(f"  JSON parse error for {candidate['name']}: {e}")
        print(f"  Raw response: {full_text[:300]}")
        return []
    except Exception as e:
        print(f"  Error fetching {candidate['name']}: {e}")
        return []

def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set")

    client = anthropic.Anthropic(api_key=api_key)
    data = load_existing_events()
    known_ids = existing_ids(data)
    new_events = []

    print(f"Starting event fetch. Existing events: {len(data['events'])}")

    for i, candidate in enumerate(CANDIDATES):
        print(f"\nFetching events for {candidate['name']}...")
        events = fetch_events_for_candidate(client, candidate)

        for event in events:
            # Ensure required fields
            if not event.get("id") or not event.get("candidate") or not event.get("date"):
                continue
            # Deduplicate
            if event["id"] in known_ids:
                print(f"  Skipping duplicate: {event['id']}")
                continue
            # Normalize press_clips
            if "press_clips" not in event or not isinstance(event["press_clips"], list):
                event["press_clips"] = []
            new_events.append(event)
            known_ids.add(event["id"])

        # Rate limit between candidates
        if i < len(CANDIDATES) - 1:
            print("  Waiting 30s before next candidate...")
            time.sleep(30)

    print(f"\nAdding {len(new_events)} new events")
    data["events"] = data["events"] + new_events

    # Sort by date descending
    data["events"].sort(key=lambda e: e.get("date", ""), reverse=True)

    save_events(data)
    print("Done!")

if __name__ == "__main__":
    main()
