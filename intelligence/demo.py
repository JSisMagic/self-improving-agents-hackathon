"""Command-line proof of the accepted feedback-to-reranking sequence."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from shared.contracts import Event, EventFeedback, UserProfile

from .actian_memory import ActianMemory
from .learning_loop import IntelligenceEngine
from .scorer import rank_events


ROOT = Path(__file__).resolve().parents[1]


def _load() -> tuple[list[Event], UserProfile, EventFeedback]:
    with (ROOT / "shared" / "sample_events.json").open(
        encoding="utf-8"
    ) as handle:
        events = [Event.from_dict(item) for item in json.load(handle)]
    with (ROOT / "shared" / "sample_profile.json").open(
        encoding="utf-8"
    ) as handle:
        profile = UserProfile.from_dict(json.load(handle))
    with (ROOT / "shared" / "sample_feedback.json").open(
        encoding="utf-8"
    ) as handle:
        feedback = EventFeedback.from_dict(json.load(handle))
    return events, profile, feedback


def main() -> None:
    events, profile, feedback = _load()
    event_titles = {event.event_id: event.title for event in events}
    before = rank_events(
        events,
        profile,
        limit=None,
        run_id="run_demo_before_v1",
    )
    mixer = next(event for event in events if event.event_id == feedback.event_id)
    mixer_before = next(
        item for item in before if item.event_id == feedback.event_id
    )

    with tempfile.TemporaryDirectory() as directory:
        engine = IntelligenceEngine(
            ActianMemory(Path(directory) / "episodes.json")
        )
        episode = engine.record_event_outcome(
            profile,
            mixer,
            feedback,
            mixer_before,
        )
        after = engine.rank_events_with_memory(
            profile,
            events,
            limit=None,
            run_id="run_demo_after_v1",
        )

        print("EVENT COPILOT — FEEDBACK-TO-RERANKING")
        print(f"Episode write: {episode.episode_id} | {engine.memory.status}")
        print("\nBEFORE FEEDBACK")
        for item in before:
            print(
                f"{item.rank}. {event_titles[item.event_id]} — "
                f"{item.scores['overall']}/100"
            )
        print("\nAFTER FEEDBACK")
        for item in after:
            influence = (
                f" | influenced by {', '.join(item.influencing_episode_ids)}"
                if item.influencing_episode_ids
                else ""
            )
            print(
                f"{item.rank}. {event_titles[item.event_id]} — "
                f"{item.scores['overall']}/100{influence}"
            )

        mixer_after = next(
            item for item in after if item.event_id == feedback.event_id
        )
        workshop_after = next(
            item
            for item in after
            if item.event_id == "evt_workshop_001"
        )
        print("\nJUDGE-FACING LEARNING MOMENT")
        print(
            f"Mixer: rank {mixer_before.rank} → {mixer_after.rank}; "
            f"score {mixer_before.scores['overall']} → "
            f"{mixer_after.scores['overall']}"
        )
        print(
            f"Workshop: rank {workshop_after.rank}; "
            f"score {workshop_after.scores['overall']}"
        )
        print(mixer_after.reasons[0])


if __name__ == "__main__":
    main()
