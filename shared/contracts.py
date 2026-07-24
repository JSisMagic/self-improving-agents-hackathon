"""Schema-aligned contracts shared by the intelligence and product modules.

The JSON Schemas in ``specs/03-data/schemas`` remain authoritative. These
lightweight dataclasses provide validation and plain-dictionary conversion for
the hackathon runtime without creating a second contract system.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from datetime import datetime
from typing import Any, TypeVar
from urllib.parse import urlparse


SCHEMA_VERSION = "1.0"
SCORING_VERSION = "v1"

T = TypeVar("T")


def _known_fields(model: type[T], data: dict[str, Any]) -> dict[str, Any]:
    """Ignore unknown optional fields within the current major schema version."""

    names = {item.name for item in fields(model)}
    return {name: value for name, value in data.items() if name in names}


def _require_nonempty(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")


def _require_range(name: str, value: float, minimum: float, maximum: float) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be numeric")
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}; got {value}")


def _require_nonnegative_integer(name: str, value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a nonnegative integer")


def _require_datetime(name: str, value: str) -> None:
    _require_nonempty(name, value)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{name} must be an ISO 8601 date-time") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{name} must include a timezone")


def _require_uri(name: str, value: str) -> None:
    _require_nonempty(name, value)
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"{name} must be an absolute HTTP(S) URL")


def _require_schema_version(value: str) -> None:
    if value != SCHEMA_VERSION:
        raise ValueError(f"schema_version must be {SCHEMA_VERSION!r}")


def _validate_citations(citations: list[dict[str, str]]) -> None:
    if not citations:
        raise ValueError("citations must contain at least one item")
    for index, citation in enumerate(citations):
        if set(citation) != {"claim", "url"}:
            raise ValueError(f"citations[{index}] must contain exactly claim and url")
        _require_nonempty(f"citations[{index}].claim", citation["claim"])
        _require_uri(f"citations[{index}].url", citation["url"])


@dataclass(slots=True)
class Event:
    schema_version: str
    data_mode: str
    event_id: str
    title: str
    description: str
    source_url: str
    source_name: str
    start_time: str
    location: str
    themes: list[str]
    format: str
    interaction_level: float
    knowledge_depth: float
    cost_usd: float
    estimated_crowd_size: int | None = None

    def __post_init__(self) -> None:
        _require_schema_version(self.schema_version)
        if self.data_mode not in {"live", "fixture"}:
            raise ValueError("data_mode must be 'live' or 'fixture'")
        for name in (
            "event_id",
            "title",
            "description",
            "source_name",
            "location",
            "format",
        ):
            _require_nonempty(name, getattr(self, name))
        _require_uri("source_url", self.source_url)
        _require_datetime("start_time", self.start_time)
        if not self.themes or any(not isinstance(item, str) or not item.strip() for item in self.themes):
            raise ValueError("themes must contain at least one non-empty string")
        _require_range("interaction_level", self.interaction_level, 0, 1)
        _require_range("knowledge_depth", self.knowledge_depth, 0, 1)
        if self.estimated_crowd_size is not None:
            _require_nonnegative_integer("estimated_crowd_size", self.estimated_crowd_size)
        if isinstance(self.cost_usd, bool) or not isinstance(self.cost_usd, (int, float)) or self.cost_usd < 0:
            raise ValueError("cost_usd must be a nonnegative number")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Event":
        return cls(**_known_fields(cls, data))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class UserProfile:
    schema_version: str
    user_id: str
    role: str
    goal_priorities: dict[str, float]
    desired_outcomes: list[str]
    preferences: dict[str, Any]
    constraints: dict[str, Any]

    def __post_init__(self) -> None:
        _require_schema_version(self.schema_version)
        _require_nonempty("user_id", self.user_id)
        _require_nonempty("role", self.role)
        required = {"networking", "knowledge", "opportunity"}
        if set(self.goal_priorities) != required:
            raise ValueError(f"goal_priorities must contain exactly {sorted(required)}")
        for name, value in self.goal_priorities.items():
            _require_range(f"goal_priorities.{name}", value, 0, 1)
        if sum(self.goal_priorities.values()) <= 0:
            raise ValueError("goal_priorities must sum to more than zero")
        if not self.desired_outcomes or any(
            not isinstance(item, str) or not item.strip() for item in self.desired_outcomes
        ):
            raise ValueError("desired_outcomes must contain at least one non-empty string")
        if not isinstance(self.preferences, dict) or not isinstance(self.constraints, dict):
            raise ValueError("preferences and constraints must be objects")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UserProfile":
        return cls(**_known_fields(cls, data))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Recommendation:
    schema_version: str
    run_id: str
    event_id: str
    rank: int
    scores: dict[str, float]
    reasons: list[str]
    influencing_episode_ids: list[str]
    confidence: float
    citations: list[dict[str, str]]
    scoring_version: str
    adjustments: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        _require_schema_version(self.schema_version)
        for name in ("run_id", "event_id", "scoring_version"):
            _require_nonempty(name, getattr(self, name))
        if isinstance(self.rank, bool) or not isinstance(self.rank, int) or self.rank < 1:
            raise ValueError("rank must be an integer greater than or equal to 1")
        required_scores = {
            "networking",
            "knowledge",
            "opportunity",
            "personal_fit",
            "friction",
            "overall",
        }
        if set(self.scores) != required_scores:
            raise ValueError(f"scores must contain exactly {sorted(required_scores)}")
        for name, value in self.scores.items():
            _require_range(f"scores.{name}", value, 0, 100)
        if not self.reasons or any(not isinstance(item, str) or not item.strip() for item in self.reasons):
            raise ValueError("reasons must contain at least one non-empty string")
        if len(self.influencing_episode_ids) != len(set(self.influencing_episode_ids)):
            raise ValueError("influencing_episode_ids must be unique")
        if any(not isinstance(item, str) or not item.strip() for item in self.influencing_episode_ids):
            raise ValueError("influencing_episode_ids must contain non-empty strings")
        _require_range("confidence", self.confidence, 0, 1)
        _validate_citations(self.citations)
        allowed_components = {
            "networking",
            "knowledge",
            "opportunity",
            "personal_fit",
            "friction",
        }
        for index, adjustment in enumerate(self.adjustments):
            required = {"component", "delta", "evidence_summary"}
            if not required.issubset(adjustment):
                raise ValueError(f"adjustments[{index}] is missing required fields")
            if adjustment["component"] not in allowed_components:
                raise ValueError(f"adjustments[{index}].component is invalid")
            if isinstance(adjustment["delta"], bool) or not isinstance(
                adjustment["delta"], (int, float)
            ):
                raise ValueError(f"adjustments[{index}].delta must be numeric")
            _require_nonempty(
                f"adjustments[{index}].evidence_summary",
                adjustment["evidence_summary"],
            )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Recommendation":
        return cls(**_known_fields(cls, data))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class EventFeedback:
    schema_version: str
    user_id: str
    event_id: str
    submitted_at: str
    meaningful_conversations: int
    contacts_exchanged: int
    followups_sent: int
    meetings_booked: int
    questions_answered: int
    actionable_insights: int
    opportunities_created: int
    energy_after: int
    overall_value: int
    free_text_feedback: str = ""

    def __post_init__(self) -> None:
        _require_schema_version(self.schema_version)
        _require_nonempty("user_id", self.user_id)
        _require_nonempty("event_id", self.event_id)
        _require_datetime("submitted_at", self.submitted_at)
        for name in (
            "meaningful_conversations",
            "contacts_exchanged",
            "followups_sent",
            "meetings_booked",
            "questions_answered",
            "actionable_insights",
            "opportunities_created",
        ):
            _require_nonnegative_integer(name, getattr(self, name))
        _require_nonnegative_integer("energy_after", self.energy_after)
        _require_nonnegative_integer("overall_value", self.overall_value)
        _require_range("energy_after", self.energy_after, 0, 10)
        _require_range("overall_value", self.overall_value, 0, 10)
        if not isinstance(self.free_text_feedback, str):
            raise ValueError("free_text_feedback must be a string")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EventFeedback":
        return cls(**_known_fields(cls, data))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class EventMission:
    schema_version: str
    mission_id: str
    user_id: str
    event_id: str
    recommendation_run_id: str
    objectives: list[dict[str, Any]]
    target_people: list[str]
    questions_to_ask: list[str]
    follow_up_plan: str
    citations: list[dict[str, str]]
    created_at: str

    def __post_init__(self) -> None:
        _require_schema_version(self.schema_version)
        for name in (
            "mission_id",
            "user_id",
            "event_id",
            "recommendation_run_id",
            "follow_up_plan",
        ):
            _require_nonempty(name, getattr(self, name))
        if not self.objectives:
            raise ValueError("objectives must contain at least one item")
        for index, objective in enumerate(self.objectives):
            if not {"metric", "target", "rationale"}.issubset(objective):
                raise ValueError(f"objectives[{index}] is missing required fields")
            _require_nonempty(f"objectives[{index}].metric", objective["metric"])
            if isinstance(objective["target"], bool) or not isinstance(
                objective["target"], (int, float)
            ) or objective["target"] < 0:
                raise ValueError(f"objectives[{index}].target must be nonnegative")
            _require_nonempty(f"objectives[{index}].rationale", objective["rationale"])
        for name, items in (
            ("target_people", self.target_people),
            ("questions_to_ask", self.questions_to_ask),
        ):
            if not items or any(not isinstance(item, str) or not item.strip() for item in items):
                raise ValueError(f"{name} must contain at least one non-empty string")
        _validate_citations(self.citations)
        _require_datetime("created_at", self.created_at)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EventMission":
        return cls(**_known_fields(cls, data))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class EventEpisode:
    schema_version: str
    episode_id: str
    user_id: str
    event_id: str
    recommendation: Recommendation
    feedback: EventFeedback
    actual_scores: dict[str, float]
    actual_event_success: float
    scoring_version: str
    observed_at: str
    storage_mode: str
    derived_versions: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        _require_schema_version(self.schema_version)
        for name in ("episode_id", "user_id", "event_id", "scoring_version"):
            _require_nonempty(name, getattr(self, name))
        if self.feedback.user_id != self.user_id:
            raise ValueError("feedback.user_id must match episode.user_id")
        if self.feedback.event_id != self.event_id:
            raise ValueError("feedback.event_id must match episode.event_id")
        if self.recommendation.event_id != self.event_id:
            raise ValueError("recommendation.event_id must match episode.event_id")
        required_scores = {"networking", "knowledge", "opportunity", "personal_fit"}
        if set(self.actual_scores) != required_scores:
            raise ValueError(f"actual_scores must contain exactly {sorted(required_scores)}")
        for name, value in self.actual_scores.items():
            _require_range(f"actual_scores.{name}", value, 0, 100)
        _require_range("actual_event_success", self.actual_event_success, 0, 100)
        _require_datetime("observed_at", self.observed_at)
        if self.storage_mode not in {"live", "fixture", "local_fallback"}:
            raise ValueError("storage_mode is invalid")
        for index, derived in enumerate(self.derived_versions):
            if not {"scoring_version", "derived_at", "actual_event_success"}.issubset(derived):
                raise ValueError(f"derived_versions[{index}] is missing required fields")
            _require_nonempty(
                f"derived_versions[{index}].scoring_version",
                derived["scoring_version"],
            )
            _require_datetime(f"derived_versions[{index}].derived_at", derived["derived_at"])
            _require_range(
                f"derived_versions[{index}].actual_event_success",
                derived["actual_event_success"],
                0,
                100,
            )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EventEpisode":
        payload = _known_fields(cls, data)
        payload["recommendation"] = Recommendation.from_dict(payload["recommendation"])
        payload["feedback"] = EventFeedback.from_dict(payload["feedback"])
        return cls(**payload)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
