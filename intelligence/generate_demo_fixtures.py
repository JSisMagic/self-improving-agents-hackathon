"""Regenerate schema-aligned deterministic fixtures for the product shell."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from shared.contracts import Event, EventFeedback, UserProfile

from .actian_memory import ActianMemory
from .learning_loop import IntelligenceEngine
from .scorer import rank_events


ROOT = Path(__file__).resolve().parents[1]


def _write(path: Path, payload: object) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")


def main() -> None:
    shared = ROOT / "shared"
    with (shared / "sample_events.json").open(encoding="utf-8") as handle:
        raw_events = json.load(handle)
    with (shared / "sample_profile.json").open(encoding="utf-8") as handle:
        profile = UserProfile.from_dict(json.load(handle))
    with (shared / "sample_feedback.json").open(encoding="utf-8") as handle:
        feedback = EventFeedback.from_dict(json.load(handle))
    events = [Event.from_dict(item) for item in raw_events]

    before = rank_events(
        events,
        profile,
        limit=None,
        run_id="run_demo_before_v1",
    )
    event = next(item for item in events if item.event_id == feedback.event_id)
    recommendation = next(
        item for item in before if item.event_id == feedback.event_id
    )

    with tempfile.TemporaryDirectory() as directory:
        memory = ActianMemory(Path(directory) / "episodes.json")
        engine = IntelligenceEngine(memory)
        episode = engine.record_event_outcome(
            profile,
            event,
            feedback,
            recommendation,
            episode_id="episode_demo_mixer_001",
            observed_at="2026-07-26T12:00:00-07:00",
            storage_mode="fixture",
        )
        after = engine.rank_events_with_memory(
            profile,
            events,
            limit=None,
            run_id="run_demo_after_v1",
        )

    before_payload = [item.to_dict() for item in before]
    after_payload = [item.to_dict() for item in after]
    episode_payload = episode.to_dict()

    _write(
        shared / "pioneer_extractions.json",
        {item["event_id"]: item for item in raw_events},
    )
    _write(shared / "mock_recommendations.json", before_payload)
    _write(shared / "recommendations_before.json", before_payload)
    _write(shared / "recommendations_after.json", after_payload)
    _write(shared / "sample_episode.json", episode_payload)
    _write(shared / "actian_memories.json", [])
    print("Generated three-event before/after fixtures and one valid episode")


if __name__ == "__main__":
    main()
