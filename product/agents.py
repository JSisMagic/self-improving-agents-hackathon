"""Visible Scout, Analyst, and Coach coordination for Event Copilot.

Connected agent orchestration is outside the active hackathon scope.  These
functions run the same three roles directly, preserve a shared run ID across
handoffs, and truthfully label the path as ``demo_fallback``.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, is_dataclass
from datetime import datetime
from hashlib import sha256
from typing import Any

from product.event_mission import create_event_mission


SCOUT_PROMPT = (
    "Return normalized, source-grounded event candidates relevant to the "
    "user's goals. Preserve each event's identity, source URL, and data mode."
)
ANALYST_PROMPT = (
    "Use the intelligence ranking interface to order candidates. Preserve "
    "scores, reasons, confidence, citations, scoring version, and memory provenance."
)
COACH_PROMPT = (
    "Challenge the selected recommendation with a grounded weakness, risk, or "
    "missing assumption before creating a measurable Event Mission."
)

INTEGRATION_STATUS = "demo_fallback"

Record = Mapping[str, Any] | object
Ranker = Callable[[Sequence[Record], Record], Sequence[Record]]


def _as_dict(value: Record, label: str) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        converted = to_dict()
        if isinstance(converted, Mapping):
            return dict(converted)
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    raise TypeError(f"{label} must be a mapping or dataclass-like object")


def _required_text(value: Record, field: str, label: str) -> str:
    record = _as_dict(value, label)
    item = record.get(field)
    if not isinstance(item, str) or not item.strip():
        raise ValueError(f"{label}.{field} must be a non-empty string")
    return item.strip()


def _canonical(value: Record) -> dict[str, Any]:
    return _as_dict(value, type(value).__name__)


def _derive_run_id(profile: Record, events: Sequence[Record]) -> str:
    payload = {
        "profile": _canonical(profile),
        "events": [_canonical(event) for event in events],
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return f"run_{sha256(encoded).hexdigest()[:12]}"


def _resolve_run_id(
    profile: Record,
    events: Sequence[Record],
    run_id: str | None,
) -> str:
    if run_id is None:
        return _derive_run_id(profile, events)
    if not isinstance(run_id, str) or not run_id.strip():
        raise ValueError("run_id must be a non-empty string")
    return run_id.strip()


def _default_ranker(
    events: Sequence[Record],
    profile: Record,
    *,
    run_id: str,
) -> Sequence[Record]:
    """Call only the public intelligence API, adapting schema-shaped mappings."""

    from intelligence import rank_events
    from shared.contracts import Event, UserProfile

    profile_value: Record = profile
    if isinstance(profile, Mapping):
        profile_value = UserProfile.from_dict(dict(profile))

    event_values: list[Record] = []
    for event in events:
        if isinstance(event, Mapping):
            event_values.append(Event.from_dict(dict(event)))
        else:
            event_values.append(event)

    return rank_events(event_values, profile_value, run_id=run_id)


def run_scout(events: Sequence[Record], *, run_id: str) -> dict[str, Any]:
    """Validate normalized candidates and prepare the Scout-to-Analyst handoff."""

    if not events:
        raise ValueError("Scout requires at least one event candidate")

    event_ids: list[str] = []
    data_modes: dict[str, str] = {}
    for event in events:
        event_data = _as_dict(event, "event")
        event_id = _required_text(event_data, "event_id", "event")
        _required_text(event_data, "title", "event")
        _required_text(event_data, "source_url", "event")
        event_ids.append(event_id)
        mode = event_data.get("data_mode")
        data_modes[event_id] = (
            mode if mode in {"live", "fixture"} else "unspecified"
        )

    summary = (
        f"Scout passed {len(event_ids)} source-grounded candidate(s) to Analyst."
    )
    return {
        "role": "Scout",
        "run_id": run_id,
        "status": "complete",
        "integration_status": INTEGRATION_STATUS,
        "summary": summary,
        "event_ids": event_ids,
        "data_modes": data_modes,
        "handoff": {
            "from": "Scout",
            "to": "Analyst",
            "run_id": run_id,
            "summary": summary,
        },
    }


def run_analyst(
    profile: Record,
    events: Sequence[Record],
    *,
    run_id: str,
    ranker: Ranker | None = None,
) -> dict[str, Any]:
    """Rank candidates through the public intelligence boundary."""

    if ranker is None:
        ranked_values = list(_default_ranker(events, profile, run_id=run_id))
    else:
        ranked_values = list(ranker(events, profile))
    if not ranked_values:
        raise ValueError("Analyst received no recommendations from intelligence")

    recommendations = [
        _as_dict(recommendation, "recommendation")
        for recommendation in ranked_values
    ]
    event_ids = {_required_text(event, "event_id", "event") for event in events}
    for recommendation in recommendations:
        recommendation_event_id = _required_text(
            recommendation, "event_id", "recommendation"
        )
        if recommendation_event_id not in event_ids:
            raise ValueError(
                "intelligence returned a recommendation for an unknown event"
            )

    top_event_id = _required_text(
        recommendations[0], "event_id", "recommendation"
    )
    summary = (
        f"Analyst ranked {len(recommendations)} candidate(s) and passed "
        f"{top_event_id} to Coach for challenge."
    )
    return {
        "role": "Analyst",
        "run_id": run_id,
        "status": "complete",
        "integration_status": INTEGRATION_STATUS,
        "summary": summary,
        "recommendations": recommendations,
        "handoff": {
            "from": "Analyst",
            "to": "Coach",
            "run_id": run_id,
            "summary": summary,
        },
    }


def _component_score(recommendation: Mapping[str, Any], name: str) -> float:
    scores = recommendation.get("scores")
    if not isinstance(scores, Mapping):
        return 0.0
    value = scores.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0.0
    return max(0.0, min(100.0, float(value)))


def _coach_critique(
    event: Mapping[str, Any],
    recommendation: Mapping[str, Any],
) -> str:
    confidence_value = recommendation.get("confidence")
    confidence = (
        float(confidence_value)
        if isinstance(confidence_value, (int, float))
        and not isinstance(confidence_value, bool)
        else None
    )
    if confidence is not None and confidence < 0.7:
        return (
            f"Risk: recommendation confidence is {confidence:.2f}; prior-outcome "
            "or grounding evidence may be limited, so validate fit during the event."
        )

    friction = _component_score(recommendation, "friction")
    if friction >= 30:
        return (
            f"Weakness: predicted friction is {friction:g}/100, which may reduce "
            "the time or energy available for the mission objectives."
        )

    components = {
        name: _component_score(recommendation, name)
        for name in ("networking", "knowledge", "opportunity", "personal_fit")
    }
    weakest_name = min(components, key=components.get)
    weakest_score = components[weakest_name]
    if weakest_score < 70:
        return (
            f"Weakness: {weakest_name.replace('_', ' ')} is the lowest predicted "
            f"outcome at {weakest_score:g}/100; the mission should test it explicitly."
        )

    crowd_size = event.get("estimated_crowd_size")
    crowd_context = (
        f" despite an estimated crowd of {crowd_size}"
        if isinstance(crowd_size, int) and crowd_size >= 0
        else ""
    )
    return (
        "Missing assumption: the recommendation does not establish that relevant "
        f"participants will be available{crowd_context}; verify roles on site "
        "without assuming access to any named person."
    )


def run_coach(
    profile: Record,
    event: Record,
    recommendation: Record,
    *,
    run_id: str,
    created_at: str | datetime | None = None,
) -> dict[str, Any]:
    """Challenge a recommendation, then create its grounded Event Mission."""

    event_data = _as_dict(event, "event")
    recommendation_data = _as_dict(recommendation, "recommendation")
    event_id = _required_text(event_data, "event_id", "event")
    if _required_text(
        recommendation_data, "event_id", "recommendation"
    ) != event_id:
        raise ValueError("recommendation.event_id must match event.event_id")

    critique = _coach_critique(event_data, recommendation_data)
    mission = create_event_mission(
        profile,
        event_data,
        recommendation_data,
        recommendation_run_id=run_id,
        created_at=created_at,
    )
    return {
        "role": "Coach",
        "run_id": run_id,
        "status": "complete",
        "integration_status": INTEGRATION_STATUS,
        "summary": (
            f"Coach challenged {event_id} before creating a measurable mission."
        ),
        "event_id": event_id,
        "critique": critique,
        "mission": mission,
    }


def run_agent_handoff(
    profile: Record,
    events: Sequence[Record],
    *,
    selected_event_id: str | None = None,
    run_id: str | None = None,
    created_at: str | datetime | None = None,
    ranker: Ranker | None = None,
) -> dict[str, Any]:
    """Execute the deterministic local Scout -> Analyst -> Coach path."""

    event_values = list(events)
    resolved_run_id = _resolve_run_id(profile, event_values, run_id)
    scout = run_scout(event_values, run_id=resolved_run_id)
    analyst = run_analyst(
        profile,
        event_values,
        run_id=resolved_run_id,
        ranker=ranker,
    )
    recommendations = analyst["recommendations"]

    chosen_event_id = selected_event_id or _required_text(
        recommendations[0], "event_id", "recommendation"
    )
    event_by_id = {
        _required_text(event, "event_id", "event"): event for event in event_values
    }
    recommendation_by_id = {
        _required_text(item, "event_id", "recommendation"): item
        for item in recommendations
    }
    if chosen_event_id not in event_by_id:
        raise ValueError(f"selected event {chosen_event_id!r} is not a candidate")
    if chosen_event_id not in recommendation_by_id:
        raise ValueError(
            f"selected event {chosen_event_id!r} has no recommendation"
        )

    coach = run_coach(
        profile,
        event_by_id[chosen_event_id],
        recommendation_by_id[chosen_event_id],
        run_id=resolved_run_id,
        created_at=created_at,
    )
    return {
        "run_id": resolved_run_id,
        "mode": INTEGRATION_STATUS,
        "integration_status": INTEGRATION_STATUS,
        "scout": scout,
        "analyst": analyst,
        "coach": coach,
        "handoffs": [scout["handoff"], analyst["handoff"]],
        "recommendations": recommendations,
        "critique": coach["critique"],
        "mission": coach["mission"],
    }
