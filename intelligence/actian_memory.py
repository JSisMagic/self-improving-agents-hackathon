"""Local JSON episode store retained behind the historical module name.

Actian integration is deferred. This implementation never claims a connected
service and exists only to keep the accepted local fallback path operational.
"""

from __future__ import annotations

import json
from pathlib import Path

from shared.contracts import Event, EventEpisode


class ActianMemory:
    """Schema-valid local fallback storage for EventEpisode objects."""

    def __init__(self, fallback_path: str | Path) -> None:
        self.fallback_path = Path(fallback_path)

    def _load(self) -> list[EventEpisode]:
        if not self.fallback_path.exists():
            return []
        with self.fallback_path.open(encoding="utf-8") as handle:
            data = json.load(handle)
        return [EventEpisode.from_dict(item) for item in data]

    def _save(self, episodes: list[EventEpisode]) -> None:
        self.fallback_path.parent.mkdir(parents=True, exist_ok=True)
        with self.fallback_path.open("w", encoding="utf-8") as handle:
            json.dump(
                [episode.to_dict() for episode in episodes],
                handle,
                indent=2,
            )
            handle.write("\n")

    @property
    def status(self) -> str:
        return f"{len(self._load())} episode(s) | local_fallback"

    def all(self, user_id: str | None = None) -> list[EventEpisode]:
        episodes = self._load()
        if user_id is None:
            return episodes
        return [episode for episode in episodes if episode.user_id == user_id]

    def retrieve_similar(
        self,
        user_id: str,
        event: Event,
        limit: int = 4,
    ) -> list[EventEpisode]:
        """Use exact event identity for the release-gate feedback loop."""

        matching = [
            episode
            for episode in self.all(user_id)
            if episode.event_id == event.event_id
        ]
        matching.sort(key=lambda item: item.observed_at, reverse=True)
        return matching[:limit]

    def record(self, episode: EventEpisode) -> None:
        episodes = [
            item
            for item in self._load()
            if item.episode_id != episode.episode_id
        ]
        episodes.append(episode)
        self._save(episodes)
