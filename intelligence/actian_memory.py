"""Actian-facing memory boundary with a JSON fallback that always works locally."""

from __future__ import annotations

import json
from pathlib import Path

from shared.contracts import Event, EventEpisode


def event_similarity(left: Event, right: Event) -> float:
    left_themes = {item.casefold() for item in left.themes}
    right_themes = {item.casefold() for item in right.themes}
    union = left_themes | right_themes
    theme_score = len(left_themes & right_themes) / len(union) if union else 0.0
    format_score = 1.0 if left.format == right.format else 0.0
    location_score = 1.0 if left.location.casefold() == right.location.casefold() else 0.0
    return 0.55 * format_score + 0.35 * theme_score + 0.10 * location_score


class ActianMemory:
    """Persistent event memory.

    The hackathon demo uses the local JSON backend. This class is the stable seam
    where an Actian VectorAI/Vector Search adapter can replace `_load` and `_save`
    without changing the ranking or product modules.
    """

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
            json.dump([episode.to_dict() for episode in episodes], handle, indent=2)
            handle.write("\n")

    @property
    def status(self) -> str:
        return f"{len(self._load())} experiences | demo fallback"

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
        minimum_similarity: float = 0.35,
    ) -> list[EventEpisode]:
        scored = [
            (event_similarity(event, episode.event), episode)
            for episode in self.all(user_id)
        ]
        scored.sort(key=lambda item: item[0], reverse=True)
        return [episode for score, episode in scored if score >= minimum_similarity][:limit]

    def record(self, episode: EventEpisode) -> None:
        episodes = [item for item in self._load() if item.episode_id != episode.episode_id]
        episodes.append(episode)
        self._save(episodes)
