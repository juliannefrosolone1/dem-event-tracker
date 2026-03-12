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

SYSTEM_PROMPT = """You are a political intelligence analyst with deep knowledge of U.S. politics
through early 2026. You track potential 2028 Democratic presidential primary candidates.

Return ONLY a valid JSON array. No preamble, no markdown, no backticks. Just raw JSON.

Each event object must have exactly these fields:
{
  "id": "candidate_id-YYYY-MM-DD-slug (e.g. booker-2025-03-15-iowa-town-hall)",
  "candidate": "candidate id string",
  "date": "YYYY-MM-DD",
  "event_type": "one of: rally, town_hall, speech, fundraiser, interview, media_appearance, endorsement, travel, other",
  "title": "short descriptive title",
  "location_city": "city name or empty string",
  "location_state": "2-letter state code or empty string",
  "location_display": "City, ST or Virtual or National",
  "venue": "venue name or empty string",
  "description": "1-2 sentence description",
  "significance": "one of: high, medium, low",
  "press_clips": [
    {
      "outlet": "news outlet name",
      "headline": "article headline",
      "url": "",
      "date": "YYYY-MM-DD"
    }
  ]
}

Only include events you are highly confident actually occurred based on your training data.
Return an empty array [] if you are not confident about specific events.
Use empty string for url since you cannot verify URLs."""

def load_existing_events():
    if EVENTS_FILE.exists():
        with open(EVENTS_FILE) as f:
            return json.load(f)
    return {"events": [], "last_updated": "", "meta": {"source": "auto-fetched via Anthropic API"}}

def save_events(data):
    data["last_updated"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(EVENTS_FILE, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Saved {len(data['events'])} total events to {EVENTS_FILE}")

def existing_ids(data):
    return {e["id"] for e in data["events"]}

def fetch_events_for_candidate(client, candidate):
    prompt = f"""From your training knowledge, list significant public events, appearances, and activities
for {candidate['name']} from January 1, 2025 through early 2026.

Include:
- Public rallies, town halls, or campaign-style events in ANY state
- Major speeches (Senate/House floor, think tanks, conferences, universities)
- TV interviews and major podcast appearances
- Travel to early primary states (Iowa, New Hampshire, Nevada, South Carolina, Georgia)
- Fundraising events
- Endorsements given or received
- Major op-eds or public statements that received national media coverage

Be specific about dates, locations, and what happened. Only include events you are genuinely
confident occurred. Aim for 5-15 significant events.

Use candidate id: "{candidate['id']}"

Return a JSON array of event objects."""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=3000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}]
        )

        full_text = ""
        for block in response.content:
            if hasattr(block, "text"):
                full_text += block.text

        full_text = full_text.strip()
        if full_text.startswith("```"):
            parts = full_text.split("```")
            full_text = parts[1] if len(parts) > 1 else full_text
            if full_text.startswith("json"):
                full_text = full_text[4:]
        full_text = full_text.strip()

        if not full_text or full_text == "[]":
            print(f"  No events returned for {candidate['name']}")
            return []

        events = json.loads(full_text)
        if not isinstance(events, list):
            print(f"  Unexpected format for {candidate['name']}")
            return []

        print(f"  Found {len(events)} events for {candidate['name']}")
        return events

    except json.JSONDecodeError as e:
        print(f"  JSON parse error for {candidate['name']}: {e}")
        print(f"  Raw (first 300): {full_text[:300]}")
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
            if not event.get("id") or not event.get("candidate") or not event.get("date"):
                continue
            if event["id"] in known_ids:
                print(f"  Skipping duplicate: {event['id']}")
                continue
            if "press_clips" not in event or not isinstance(event["press_clips"], list):
                event["press_clips"] = []
            new_events.append(event)
            known_ids.add(event["id"])

        if i < len(CANDIDATES) - 1:
            print("  Waiting 10s before next candidate...")
            time.sleep(10)

    print(f"\nAdding {len(new_events)} new events")
    data["events"] = data["events"] + new_events
    data["events"].sort(key=lambda e: e.get("date", ""), reverse=True)

    save_events(data)
    print("Done!")

if __name__ == "__main__":
    main()
