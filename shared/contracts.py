"""Stable JSON contracts shared by the intelligence and product modules.

The dataclasses intentionally accept and emit plain dictionaries so Hasan's UI can
consume the intelligence output without importing the implementation modules.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


def _require_range(name: str, value: float, minimum: float, maximum: float) -> None:
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}; got {value}")


@dataclass(slots=True)
class Event:
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
    estimated_crowd_size: int
    cost_usd: float

    def __post_init__(self) -> None:
        if not self.event_id or not self.title:
            raise ValueError("event_id and title are required")
        _require_range("interaction_level", self.interaction_level, 0, 1)
        _require_range("knowledge_depth", self.knowledge_depth, 0, 1)
        if self.estimated_crowd_size < 0 or self.cost_usd < 0:
            raise ValueError("estimated_crowd_size and cost_usd cannot be negative")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Event":
        return cls(**data)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class UserProfile:
    user_id: str
    name: str
    location: str
    interests: list[str]
    goal_weights: dict[str, float]
    preferred_formats: list[str] = field(default_factory=list)
    max_cost_usd: float = 100.0
    preferred_max_crowd_size: int = 150

    def __post_init__(self) -> None:
        required = {"networking", "knowledge", "opportunity", "personal_fit"}
        if set(self.goal_weights) != required:
            raise ValueError(f"goal_weights must contain exactly {sorted(required)}")
        for name, value in self.goal_weights.items():
            _require_range(f"goal_weights.{name}", value, 0, 1)
        if abs(sum(self.goal_weights.values()) - 1.0) > 0.001:
            raise ValueError("goal_weights must sum to 1.0")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UserProfile":
        return cls(**data)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Recommendation:
    event_id: str
    scores: dict[str, int]
    reasons: list[str]
    similar_past_events: list[str]
    confidence: float
    citations: list[dict[str, str]]

    def __post_init__(self) -> None:
        required = {"networking", "knowledge", "opportunity", "personal_fit", "friction", "overall"}
        if set(self.scores) != required:
            raise ValueError(f"scores must contain exactly {sorted(required)}")
        for name, value in self.scores.items():
            _require_range(f"scores.{name}", value, 0, 100)
        _require_range("confidence", self.confidence, 0, 1)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Recommendation":
        return cls(**data)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class EventFeedback:
    event_id: str
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
        count_fields = (
            "meaningful_conversations",
            "contacts_exchanged",
            "followups_sent",
            "meetings_booked",
            "questions_answered",
            "actionable_insights",
            "opportunities_created",
        )
        if any(getattr(self, name) < 0 for name in count_fields):
            raise ValueError("feedback counts cannot be negative")
        _require_range("energy_after", self.energy_after, 0, 10)
        _require_range("overall_value", self.overall_value, 0, 10)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EventFeedback":
        return cls(**data)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class EventEpisode:
    episode_id: str
    user_id: str
    event: Event
    feedback: EventFeedback
    recorded_at: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EventEpisode":
        payload = dict(data)
        payload["event"] = Event.from_dict(payload["event"])
        payload["feedback"] = EventFeedback.from_dict(payload["feedback"])
        return cls(**payload)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
