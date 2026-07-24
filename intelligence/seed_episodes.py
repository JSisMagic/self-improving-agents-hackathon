"""Load the single schema-valid demo episode into the local fallback store.

This compatibility helper does not connect to Actian and is not part of the
release-gate journey. The real demo writes an episode only after feedback.
"""

from __future__ import annotations

import json
from pathlib import Path

from shared.contracts import EventEpisode


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    shared = ROOT / "shared"
    with (shared / "sample_episode.json").open(encoding="utf-8") as handle:
        episode = EventEpisode.from_dict(json.load(handle))
    output = shared / "actian_memories.json"
    with output.open("w", encoding="utf-8") as handle:
        json.dump([episode.to_dict()], handle, indent=2)
        handle.write("\n")
    print(f"Wrote one fixture episode to {output}")


if __name__ == "__main__":
    main()
