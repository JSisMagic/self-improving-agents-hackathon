"""Connected Actian VectorAI episode memory with a truthful JSON fallback.

The shared EventEpisode contract remains the auditable learning record. Actian
stores the record as payload and indexes a stable event fingerprint for
same-user semantic retrieval. The local JSON implementation remains available
for deterministic offline operation and as a hot fallback for connected runs.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
from typing import Any, Callable, Protocol
from uuid import NAMESPACE_URL, uuid5

from shared.contracts import SCHEMA_VERSION, Event, EventEpisode


DEFAULT_ACTIAN_URL = "localhost:6574"
DEFAULT_COLLECTION = "event_copilot_episodes_v1"
DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_EMBEDDING_DIMENSION = 384
DEFAULT_RETRIEVAL_LIMIT = 4
LOCAL_SIMILARITY_THRESHOLD = 0.55


@dataclass(frozen=True, slots=True)
class RetrievalEvidence:
    """Provider-local provenance for one retrieved episode."""

    episode_id: str
    relevance: float
    provider: str
    storage_mode: str
    reason: str


class EpisodeMemory(Protocol):
    """Small intelligence-owned boundary used by the learning loop."""

    @property
    def provider(self) -> str: ...

    @property
    def mode(self) -> str: ...

    @property
    def storage_mode(self) -> str: ...

    @property
    def status(self) -> str: ...

    @property
    def last_retrieval_evidence(self) -> tuple[RetrievalEvidence, ...]: ...

    def retrieve_similar(
        self,
        user_id: str,
        event: Event,
        limit: int = DEFAULT_RETRIEVAL_LIMIT,
    ) -> list[EventEpisode]: ...

    def record(self, episode: EventEpisode, event: Event | None = None) -> None: ...

    def close(self) -> None: ...


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _safe_number(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if math.isfinite(value) else default


def event_fingerprint(event: Event) -> str:
    """Return the canonical text embedded for both writes and searches."""

    crowd = (
        str(event.estimated_crowd_size)
        if event.estimated_crowd_size is not None
        else "unknown"
    )
    return "\n".join(
        (
            f"title: {event.title}",
            f"description: {event.description}",
            f"themes: {', '.join(event.themes)}",
            f"format: {event.format}",
            f"location: {event.location}",
            f"interaction level: {event.interaction_level:.2f}",
            f"knowledge depth: {event.knowledge_depth:.2f}",
            f"estimated crowd size: {crowd}",
        )
    )


def _episode_fallback_fingerprint(episode: EventEpisode) -> str:
    """Build a deterministic fallback only for callers without Event context."""

    feedback_text = episode.feedback.free_text_feedback or ""
    return "\n".join(
        (
            f"event id: {episode.event_id}",
            f"recommendation reasons: {' '.join(episode.recommendation.reasons)}",
            f"feedback: {feedback_text}",
        )
    )


def _structured_event_similarity(left: Event, right: Event) -> float:
    """Return a deterministic fallback similarity without claiming vectors."""

    left_themes = {item.casefold() for item in left.themes}
    right_themes = {item.casefold() for item in right.themes}
    theme_union = left_themes | right_themes
    theme_similarity = (
        len(left_themes & right_themes) / len(theme_union)
        if theme_union
        else 0.0
    )
    left_location = left.location.casefold()
    right_location = right.location.casefold()
    location_similarity = float(
        left_location == right_location
        or left_location in right_location
        or right_location in left_location
    )
    format_similarity = float(left.format.casefold() == right.format.casefold())
    interaction_similarity = 1.0 - abs(
        left.interaction_level - right.interaction_level
    )
    knowledge_similarity = 1.0 - abs(
        left.knowledge_depth - right.knowledge_depth
    )
    if (
        left.estimated_crowd_size is None
        or right.estimated_crowd_size is None
    ):
        crowd_similarity = 0.5
    else:
        larger_crowd = max(
            1,
            left.estimated_crowd_size,
            right.estimated_crowd_size,
        )
        crowd_similarity = (
            min(left.estimated_crowd_size, right.estimated_crowd_size)
            / larger_crowd
        )

    return (
        0.35 * theme_similarity
        + 0.15 * format_similarity
        + 0.15 * location_similarity
        + 0.15 * interaction_similarity
        + 0.10 * knowledge_similarity
        + 0.10 * crowd_similarity
    )


class LocalEpisodeMemory:
    """Schema-valid JSON storage used for offline and degraded operation."""

    provider = "local_json"
    mode = "demo_fallback"
    storage_mode = "local_fallback"

    def __init__(self, fallback_path: str | Path) -> None:
        self.fallback_path = Path(fallback_path)
        self.event_metadata_path = self.fallback_path.with_name(
            f"{self.fallback_path.stem}.events.json"
        )
        self._last_retrieval_evidence: tuple[RetrievalEvidence, ...] = ()
        self._status_note: str | None = None

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

    def _load_event_metadata(self) -> dict[str, Event]:
        if not self.event_metadata_path.exists():
            return {}
        with self.event_metadata_path.open(encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            return {}
        return {
            str(episode_id): Event.from_dict(event)
            for episode_id, event in data.items()
            if isinstance(event, dict)
        }

    def _save_event_metadata(self, events: dict[str, Event]) -> None:
        self.event_metadata_path.parent.mkdir(parents=True, exist_ok=True)
        with self.event_metadata_path.open("w", encoding="utf-8") as handle:
            json.dump(
                {
                    episode_id: event.to_dict()
                    for episode_id, event in events.items()
                },
                handle,
                indent=2,
            )
            handle.write("\n")

    @property
    def status(self) -> str:
        base = f"{len(self._load())} episode(s) | local_fallback"
        return f"{base} | {self._status_note}" if self._status_note else base

    @property
    def last_retrieval_evidence(self) -> tuple[RetrievalEvidence, ...]:
        return self._last_retrieval_evidence

    def note_unavailable(self, provider: str, error: BaseException) -> None:
        """Record only a sanitized error class for operator truthfulness."""

        self._status_note = f"{provider} unavailable ({type(error).__name__})"

    def all(self, user_id: str | None = None) -> list[EventEpisode]:
        episodes = self._load()
        if user_id is None:
            return episodes
        return [episode for episode in episodes if episode.user_id == user_id]

    def retrieve_similar(
        self,
        user_id: str,
        event: Event,
        limit: int = DEFAULT_RETRIEVAL_LIMIT,
    ) -> list[EventEpisode]:
        """Use deterministic structured similarity for the fallback path."""

        metadata = self._load_event_metadata()
        scored: list[tuple[float, EventEpisode]] = []
        for episode in self.all(user_id):
            if episode.event_id == event.event_id:
                scored.append((1.0, episode))
                continue
            source_event = metadata.get(episode.episode_id)
            if source_event is None:
                continue
            relevance = _structured_event_similarity(source_event, event)
            if relevance >= LOCAL_SIMILARITY_THRESHOLD:
                scored.append((relevance, episode))
        scored.sort(
            key=lambda item: (item[0], item[1].observed_at),
            reverse=True,
        )
        selected = scored[:limit]
        self._last_retrieval_evidence = tuple(
            RetrievalEvidence(
                episode_id=episode.episode_id,
                relevance=relevance,
                provider=self.provider,
                storage_mode=episode.storage_mode,
                reason=(
                    "same user and exact event identity"
                    if relevance == 1.0
                    else "same user and deterministic structured event similarity"
                ),
            )
            for relevance, episode in selected
        )
        return [episode for _, episode in selected]

    def record(self, episode: EventEpisode, event: Event | None = None) -> None:
        if episode.storage_mode != "fixture":
            episode.storage_mode = self.storage_mode
        episodes = [
            item
            for item in self._load()
            if item.episode_id != episode.episode_id
        ]
        episodes.append(episode)
        self._save(episodes)
        if event is not None:
            metadata = self._load_event_metadata()
            metadata[episode.episode_id] = event
            self._save_event_metadata(metadata)

    def close(self) -> None:
        """The local backend owns no open resources."""


class ActianMemory(LocalEpisodeMemory):
    """Backward-compatible name for the historical JSON fallback."""


class ActianVectorMemory:
    """Actian VectorAI-backed semantic storage for EventEpisode objects."""

    provider = "actian_vectorai"
    mode = "connected"
    storage_mode = "live"

    def __init__(
        self,
        *,
        url: str = DEFAULT_ACTIAN_URL,
        collection: str = DEFAULT_COLLECTION,
        embedding_model: str = DEFAULT_EMBEDDING_MODEL,
        dimension: int = DEFAULT_EMBEDDING_DIMENSION,
        score_threshold: float | None = None,
        embedder: Callable[[str], list[float]] | None = None,
        sdk: Any | None = None,
        client_factory: Callable[[], Any] | None = None,
    ) -> None:
        if dimension < 1:
            raise ValueError("Actian embedding dimension must be positive")
        self.url = url
        self.collection = collection
        self.embedding_model = embedding_model
        self.dimension = dimension
        self.score_threshold = score_threshold
        self._sdk = sdk or self._load_sdk()
        self._client_factory = client_factory or (
            lambda: self._sdk.VectorAIClient(self.url)
        )
        self._last_count = 0
        self._last_retrieval_evidence: tuple[RetrievalEvidence, ...] = ()
        self._initialize()
        self._embedder = embedder or self._load_embedder(embedding_model)

    @staticmethod
    def _load_sdk() -> Any:
        try:
            import actian_vectorai
        except ImportError as exc:
            raise RuntimeError(
                "Actian SDK is unavailable; install requirements-actian.txt"
            ) from exc
        return actian_vectorai

    @staticmethod
    def _load_embedder(model_name: str) -> Callable[[str], list[float]]:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError(
                "sentence-transformers is unavailable; "
                "install requirements-actian.txt"
            ) from exc
        model = SentenceTransformer(model_name)

        def embed(text: str) -> list[float]:
            vector = model.encode(text)
            return vector.tolist() if hasattr(vector, "tolist") else list(vector)

        return embed

    def _client(self) -> Any:
        return self._client_factory()

    def _initialize(self) -> None:
        with self._client() as client:
            client.health_check()
            client.collections.get_or_create(
                name=self.collection,
                vectors_config=self._sdk.VectorParams(
                    size=self.dimension,
                    distance=self._sdk.Distance.Cosine,
                ),
            )
            self._last_count = int(
                client.vde.get_vector_count(self.collection) or 0
            )

    def _embed(self, text: str) -> list[float]:
        vector = [float(value) for value in self._embedder(text)]
        if len(vector) != self.dimension:
            raise ValueError(
                "Embedding dimension mismatch: "
                f"expected {self.dimension}, received {len(vector)}"
            )
        if any(not math.isfinite(value) for value in vector):
            raise ValueError("Embedding contains a non-finite value")
        return vector

    def _user_filter(self, user_id: str) -> Any:
        return (
            self._sdk.FilterBuilder()
            .must(self._sdk.Field("user_id").eq(user_id))
            .must(self._sdk.Field("schema_version").eq(SCHEMA_VERSION))
            .build()
        )

    @property
    def status(self) -> str:
        return (
            f"{self._last_count} episode(s) | connected | "
            f"{self.provider} | {self.collection}"
        )

    @property
    def last_retrieval_evidence(self) -> tuple[RetrievalEvidence, ...]:
        return self._last_retrieval_evidence

    def record(self, episode: EventEpisode, event: Event | None = None) -> None:
        if episode.storage_mode != "fixture":
            episode.storage_mode = self.storage_mode
        fingerprint = (
            event_fingerprint(event)
            if event is not None
            else _episode_fallback_fingerprint(episode)
        )
        point = self._sdk.PointStruct(
            id=str(
                uuid5(
                    NAMESPACE_URL,
                    f"event-copilot:{episode.episode_id}",
                )
            ),
            vector=self._embed(fingerprint),
            payload={
                "schema_version": episode.schema_version,
                "episode_id": episode.episode_id,
                "user_id": episode.user_id,
                "event_id": episode.event_id,
                "scoring_version": episode.scoring_version,
                "observed_at": episode.observed_at,
                "actual_event_success": episode.actual_event_success,
                "event_fingerprint": fingerprint,
                "episode": episode.to_dict(),
            },
        )
        with self._client() as client:
            client.points.upsert(self.collection, points=[point])
            client.vde.flush(self.collection)
            self._last_count = int(
                client.vde.get_vector_count(self.collection) or 0
            )

    def retrieve_similar(
        self,
        user_id: str,
        event: Event,
        limit: int = DEFAULT_RETRIEVAL_LIMIT,
    ) -> list[EventEpisode]:
        if limit < 1:
            self._last_retrieval_evidence = ()
            return []
        search_options: dict[str, Any] = {
            "vector": self._embed(event_fingerprint(event)),
            "limit": limit,
            "with_payload": True,
            "filter": self._user_filter(user_id),
        }
        if self.score_threshold is not None:
            search_options["score_threshold"] = self.score_threshold
        with self._client() as client:
            results = client.points.search(
                self.collection,
                **search_options,
            ) or []

        episodes: list[EventEpisode] = []
        evidence: list[RetrievalEvidence] = []
        for result in results:
            payload = getattr(result, "payload", None)
            if not isinstance(payload, dict):
                continue
            raw_episode = payload.get("episode")
            if not isinstance(raw_episode, dict):
                continue
            episode = EventEpisode.from_dict(raw_episode)
            if episode.user_id != user_id:
                continue
            relevance = float(getattr(result, "score", 0.0))
            episodes.append(episode)
            evidence.append(
                RetrievalEvidence(
                    episode_id=episode.episode_id,
                    relevance=relevance,
                    provider=self.provider,
                    storage_mode=episode.storage_mode,
                    reason="same-user semantic event-feature match",
                )
            )
        self._last_retrieval_evidence = tuple(evidence)
        return episodes

    def close(self) -> None:
        """Clients are scoped per operation; no connection remains open."""


class ResilientEpisodeMemory:
    """Use Actian while healthy and retain a session-local hot fallback."""

    def __init__(
        self,
        primary: ActianVectorMemory,
        fallback: LocalEpisodeMemory,
    ) -> None:
        self.primary = primary
        self.fallback = fallback
        self._degraded = False
        self._last_error_type: str | None = None
        self._last_retrieval_evidence: tuple[RetrievalEvidence, ...] = ()

    @property
    def provider(self) -> str:
        return self.fallback.provider if self._degraded else self.primary.provider

    @property
    def mode(self) -> str:
        return "demo_fallback" if self._degraded else "connected"

    @property
    def storage_mode(self) -> str:
        return "local_fallback" if self._degraded else "live"

    @property
    def status(self) -> str:
        if not self._degraded:
            return self.primary.status
        return (
            f"{self.fallback.status} | Actian degraded "
            f"({self._last_error_type or 'provider_error'})"
        )

    @property
    def last_retrieval_evidence(self) -> tuple[RetrievalEvidence, ...]:
        return self._last_retrieval_evidence

    def _degrade(self, error: BaseException) -> None:
        self._degraded = True
        self._last_error_type = type(error).__name__
        self.fallback.note_unavailable(self.primary.provider, error)

    @staticmethod
    def _fallback_copy(episode: EventEpisode) -> EventEpisode:
        copy = EventEpisode.from_dict(episode.to_dict())
        if copy.storage_mode != "fixture":
            copy.storage_mode = "local_fallback"
        return copy

    def record(self, episode: EventEpisode, event: Event | None = None) -> None:
        if episode.storage_mode == "fixture":
            self.fallback.record(episode, event)
            return
        if not self._degraded:
            try:
                self.primary.record(episode, event)
                self.fallback.record(self._fallback_copy(episode), event)
                return
            except Exception as exc:
                self._degrade(exc)
        episode.storage_mode = "local_fallback"
        self.fallback.record(episode, event)

    def retrieve_similar(
        self,
        user_id: str,
        event: Event,
        limit: int = DEFAULT_RETRIEVAL_LIMIT,
    ) -> list[EventEpisode]:
        if not self._degraded:
            try:
                episodes = self.primary.retrieve_similar(user_id, event, limit)
                self._last_retrieval_evidence = (
                    self.primary.last_retrieval_evidence
                )
                return episodes
            except Exception as exc:
                self._degrade(exc)
        episodes = self.fallback.retrieve_similar(user_id, event, limit)
        self._last_retrieval_evidence = self.fallback.last_retrieval_evidence
        return episodes

    def all(self, user_id: str | None = None) -> list[EventEpisode]:
        """Expose the hot fallback for diagnostics without scanning Actian."""

        return self.fallback.all(user_id)

    def close(self) -> None:
        self.primary.close()
        self.fallback.close()


def create_episode_memory(
    fallback_path: str | Path,
) -> EpisodeMemory:
    """Create the configured memory without making Actian demo-critical.

    Actian is opt-in so installing the optional dependencies alone never
    changes the deterministic local path. Startup failures are sanitized and
    returned as a labeled local fallback rather than breaking the UI.
    """

    fallback = LocalEpisodeMemory(fallback_path)
    if not _truthy(os.getenv("ACTIAN_VECTORAI_ENABLED")):
        return fallback

    dimension = int(
        _safe_number(
            "ACTIAN_EMBEDDING_DIMENSION",
            DEFAULT_EMBEDDING_DIMENSION,
        )
    )
    threshold_raw = os.getenv("ACTIAN_SCORE_THRESHOLD")
    threshold = (
        _safe_number("ACTIAN_SCORE_THRESHOLD", 0.0)
        if threshold_raw not in {None, ""}
        else None
    )
    try:
        primary = ActianVectorMemory(
            url=os.getenv("ACTIAN_VECTORAI_URL", DEFAULT_ACTIAN_URL),
            collection=os.getenv(
                "ACTIAN_VECTORAI_COLLECTION",
                DEFAULT_COLLECTION,
            ),
            embedding_model=os.getenv(
                "ACTIAN_EMBEDDING_MODEL",
                DEFAULT_EMBEDDING_MODEL,
            ),
            dimension=dimension,
            score_threshold=threshold,
        )
    except Exception as exc:
        fallback.note_unavailable("actian_vectorai", exc)
        return fallback
    return ResilientEpisodeMemory(primary, fallback)
