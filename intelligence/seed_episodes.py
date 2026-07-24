"""Generate the eight deterministic outcomes used by the learning-loop demo."""

from __future__ import annotations

import json
from pathlib import Path

from shared.contracts import Event, EventEpisode, EventFeedback


ROOT = Path(__file__).resolve().parents[1]


def _feedback(event_id: str, kind: str) -> EventFeedback:
    fixtures = {
        "mixer_low": dict(
            meaningful_conversations=7,
            contacts_exchanged=6,
            followups_sent=0,
            meetings_booked=0,
            questions_answered=1,
            actionable_insights=1,
            opportunities_created=0,
            energy_after=4,
            overall_value=5,
            free_text_feedback="Many conversations but no useful follow-up.",
        ),
        "workshop_high": dict(
            meaningful_conversations=4,
            contacts_exchanged=3,
            followups_sent=4,
            meetings_booked=2,
            questions_answered=4,
            actionable_insights=3,
            opportunities_created=2,
            energy_after=9,
            overall_value=9,
            free_text_feedback="Smaller hands-on sessions created durable relationships and insights.",
        ),
        "roundtable_high": dict(
            meaningful_conversations=5,
            contacts_exchanged=4,
            followups_sent=3,
            meetings_booked=1,
            questions_answered=3,
            actionable_insights=3,
            opportunities_created=1,
            energy_after=8,
            overall_value=9,
            free_text_feedback="Facilitated peer discussion led to one concrete opportunity.",
        ),
        "hackathon_good": dict(
            meaningful_conversations=6,
            contacts_exchanged=4,
            followups_sent=2,
            meetings_booked=1,
            questions_answered=3,
            actionable_insights=2,
            opportunities_created=1,
            energy_after=7,
            overall_value=8,
            free_text_feedback="Building together produced useful technical and social outcomes.",
        ),
    }
    return EventFeedback(event_id=event_id, **fixtures[kind])


def build_seed_episodes() -> list[EventEpisode]:
    with (ROOT / "shared" / "sample_events.json").open(encoding="utf-8") as handle:
        current = {item["event_id"]: Event.from_dict(item) for item in json.load(handle)}

    specs = [
        ("episode_001", "evt_001", "mixer", "mixer_low"),
        ("episode_002", "evt_001", "mixer", "mixer_low"),
        ("episode_003", "evt_001", "mixer", "mixer_low"),
        ("episode_004", "evt_002", "workshop", "workshop_high"),
        ("episode_005", "evt_002", "workshop", "workshop_high"),
        ("episode_006", "evt_002", "workshop", "workshop_high"),
        ("episode_007", "evt_003", "roundtable", "roundtable_high"),
        ("episode_008", "evt_004", "hackathon", "hackathon_good"),
    ]
    episodes: list[EventEpisode] = []
    for index, (episode_id, source_id, event_format, feedback_kind) in enumerate(specs, start=1):
        source = current[source_id].to_dict()
        past_event_id = f"past_{event_format}_{index:02d}"
        source.update(
            event_id=past_event_id,
            title=f"Past {source['title']} #{index}",
            source_url=f"https://example.com/history/{past_event_id}",
            start_time=f"2026-0{min(index, 6)}-15T18:00:00-07:00",
        )
        event = Event.from_dict(source)
        episodes.append(
            EventEpisode(
                episode_id=episode_id,
                user_id="demo_gergana",
                event=event,
                feedback=_feedback(event.event_id, feedback_kind),
                recorded_at=f"2026-0{min(index, 6)}-16T12:00:00+00:00",
            )
        )
    return episodes


def main() -> None:
    output = ROOT / "shared" / "actian_memories.json"
    with output.open("w", encoding="utf-8") as handle:
        json.dump([episode.to_dict() for episode in build_seed_episodes()], handle, indent=2)
        handle.write("\n")
    print(f"Wrote 8 seeded experiences to {output}")


if __name__ == "__main__":
    main()
