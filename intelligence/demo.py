"""Command-line proof of the Event Copilot learning loop."""

from __future__ import annotations

import json
from pathlib import Path

from shared.contracts import Event, UserProfile

from .learning_loop import default_engine
from .scorer import rank_events


ROOT = Path(__file__).resolve().parents[1]


def _load() -> tuple[list[Event], UserProfile]:
    with (ROOT / "shared" / "sample_events.json").open(encoding="utf-8") as handle:
        events = [Event.from_dict(item) for item in json.load(handle)]
    with (ROOT / "shared" / "sample_profile.json").open(encoding="utf-8") as handle:
        profile = UserProfile.from_dict(json.load(handle))
    return events, profile


def main() -> None:
    events, profile = _load()
    engine = default_engine()
    event_titles = {event.event_id: event.title for event in events}
    before = rank_events(events, profile)
    after = engine.rank_events_with_memory(profile, events)

    print("EVENT COPILOT — EVIDENCE-BASED RERANKING")
    print(f"Actian memory: {engine.memory.status}\n")
    print("BEFORE MEMORY")
    for index, item in enumerate(before, start=1):
        print(f"{index}. {event_titles[item.event_id]} — {item.scores['overall']}/100")
    print("\nAFTER MEMORY")
    for index, item in enumerate(after, start=1):
        print(f"{index}. {event_titles[item.event_id]} — {item.scores['overall']}/100")
        print(f"   {item.reasons[0]}")

    mixer_before = next(item for item in before if item.event_id == "evt_001")
    mixer_after = next(item for item in engine.rank_events_with_memory(profile, events, limit=None) if item.event_id == "evt_001")
    workshop_before = next(item for item in rank_events(events, profile, limit=None) if item.event_id == "evt_002")
    workshop_after = next(item for item in after if item.event_id == "evt_002")
    print("\nJUDGE-FACING LEARNING MOMENT")
    print(f"Mixer: {mixer_before.scores['overall']} → {mixer_after.scores['overall']}")
    print(f"Workshop: {workshop_before.scores['overall']} → {workshop_after.scores['overall']}")


if __name__ == "__main__":
    main()
