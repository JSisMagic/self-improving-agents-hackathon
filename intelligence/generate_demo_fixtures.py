"""Refresh contract-compatible fixtures consumed by Hasan's product shell."""

from __future__ import annotations

import json
from pathlib import Path

from shared.contracts import Event, UserProfile

from .learning_loop import default_engine
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
    events = [Event.from_dict(item) for item in raw_events]

    before = rank_events(events, profile, limit=None)
    after = default_engine().rank_events_with_memory(profile, events, limit=None)
    before_payload = [item.to_dict() for item in before]
    after_payload = [item.to_dict() for item in after]

    _write(shared / "pioneer_extractions.json", {item["event_id"]: item for item in raw_events})
    _write(shared / "mock_recommendations.json", before_payload[:3])
    _write(shared / "recommendations_before.json", before_payload)
    _write(shared / "recommendations_after.json", after_payload)
    print("Generated Pioneer cache and before/after recommendation fixtures")


if __name__ == "__main__":
    main()
