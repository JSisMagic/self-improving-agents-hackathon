"""Deterministic version-1 scoring for the canonical demo candidates."""

from __future__ import annotations

from dataclasses import replace

from shared.contracts import (
    SCHEMA_VERSION,
    SCORING_VERSION,
    Event,
    Recommendation,
    UserProfile,
)


FORMAT_NETWORKING = {
    "mixer": 1.00,
    "roundtable": 0.92,
    "hackathon": 0.88,
    "workshop": 0.78,
    "office-hours": 0.80,
    "demo-day": 0.82,
    "conference": 0.60,
    "seminar": 0.35,
}
FORMAT_KNOWLEDGE = {
    "workshop": 1.00,
    "seminar": 0.96,
    "hackathon": 0.90,
    "roundtable": 0.84,
    "office-hours": 0.78,
    "conference": 0.72,
    "demo-day": 0.58,
    "mixer": 0.35,
}
FORMAT_OPPORTUNITY = {
    "mixer": 1.00,
    "demo-day": 0.95,
    "office-hours": 0.90,
    "hackathon": 0.85,
    "roundtable": 0.82,
    "workshop": 0.72,
    "conference": 0.70,
    "seminar": 0.45,
}


def clamp_score(value: float) -> int:
    return round(max(0.0, min(100.0, value)))


def _profile_themes(profile: UserProfile) -> list[str]:
    raw = profile.preferences.get("themes", [])
    return [str(item) for item in raw] if isinstance(raw, list) else []


def _preferred_formats(profile: UserProfile) -> list[str]:
    raw = profile.preferences.get("formats", [])
    return [str(item) for item in raw] if isinstance(raw, list) else []


def _theme_match(event: Event, profile: UserProfile) -> float:
    interests = [item.casefold() for item in _profile_themes(profile)]
    themes = [item.casefold() for item in event.themes]
    if not interests:
        return 0.5
    matches = sum(
        any(interest in theme or theme in interest for theme in themes)
        for interest in interests
    )
    return min(1.0, matches / min(2, len(interests)))


def _constraint_number(profile: UserProfile, name: str, default: float) -> float:
    value = profile.constraints.get(name, default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _profile_location(profile: UserProfile) -> str:
    return str(profile.constraints.get("location", "")).strip()


def _friction(event: Event, profile: UserProfile) -> int:
    max_cost = max(1.0, _constraint_number(profile, "max_cost_usd", 100.0))
    cost_penalty = 0.0
    if event.cost_usd > max_cost:
        cost_penalty = min(
            60.0,
            20 + 40 * (event.cost_usd - max_cost) / max_cost,
        )

    preferred_crowd = max(
        1.0,
        _constraint_number(profile, "preferred_max_crowd_size", 150.0),
    )
    crowd_penalty = 0.0
    if (
        event.estimated_crowd_size is not None
        and event.estimated_crowd_size > preferred_crowd
    ):
        excess_ratio = event.estimated_crowd_size / preferred_crowd - 1
        crowd_penalty = min(18.0, excess_ratio * 8)

    profile_location = _profile_location(profile)
    location_penalty = (
        0
        if profile_location
        and profile_location.casefold() in event.location.casefold()
        else 8
    )
    return clamp_score(cost_penalty + crowd_penalty + location_penalty)


def _outcome_weights(profile: UserProfile) -> dict[str, float]:
    """Normalize the three goal priorities to 90%; personal fit keeps 10%."""

    priority_total = sum(profile.goal_priorities.values())
    return {
        name: 0.9 * value / priority_total
        for name, value in profile.goal_priorities.items()
    }


def overall_score(
    components: dict[str, float],
    friction: float,
    profile: UserProfile,
) -> int:
    weights = _outcome_weights(profile)
    predicted_outcome = sum(
        components[name] * weights[name]
        for name in ("networking", "knowledge", "opportunity")
    ) + 0.10 * components["personal_fit"]
    return clamp_score(predicted_outcome - 0.15 * friction)


def score_event(
    event: Event,
    profile: UserProfile,
    *,
    run_id: str = "run_local_v1",
    rank: int = 1,
) -> Recommendation:
    crowd_access = (
        0.5
        if event.estimated_crowd_size is None
        else min(1.0, event.estimated_crowd_size / 150)
    )
    networking = clamp_score(
        55 * event.interaction_level
        + 30 * FORMAT_NETWORKING.get(event.format, 0.55)
        + 15 * crowd_access
    )
    knowledge = clamp_score(
        72 * event.knowledge_depth
        + 28 * FORMAT_KNOWLEDGE.get(event.format, 0.60)
    )
    opportunity = clamp_score(
        45 * event.interaction_level
        + 30 * crowd_access
        + 25 * FORMAT_OPPORTUNITY.get(event.format, 0.60)
    )
    match = _theme_match(event, profile)
    format_match = 1.0 if event.format in _preferred_formats(profile) else 0.35
    profile_location = _profile_location(profile)
    location_match = (
        1.0
        if profile_location
        and profile_location.casefold() in event.location.casefold()
        else 0.45
    )
    personal_fit = clamp_score(
        70 * match + 20 * format_match + 10 * location_match
    )
    friction = _friction(event, profile)

    component_scores = {
        "networking": networking,
        "knowledge": knowledge,
        "opportunity": opportunity,
        "personal_fit": personal_fit,
    }
    overall = overall_score(component_scores, friction, profile)

    strongest = max(component_scores, key=component_scores.get)
    reasons = [
        f"The strongest predicted outcome is {strongest} ({component_scores[strongest]}/100).",
        f"The event matches {round(match * 100)}% of the demo profile's priority themes.",
    ]
    if friction >= 25:
        reasons.append(
            f"Cost, crowd size, or travel creates {friction}/100 friction."
        )

    confidence = 0.80 if event.data_mode == "live" else 0.60
    return Recommendation(
        schema_version=SCHEMA_VERSION,
        run_id=run_id,
        event_id=event.event_id,
        rank=rank,
        scores={**component_scores, "friction": friction, "overall": overall},
        reasons=reasons,
        influencing_episode_ids=[],
        confidence=confidence,
        citations=[{"claim": event.description, "url": event.source_url}],
        scoring_version=SCORING_VERSION,
    )


def rank_events(
    events: list[Event],
    profile: UserProfile,
    limit: int | None = 3,
    *,
    run_id: str = "run_local_v1",
) -> list[Recommendation]:
    ranked = sorted(
        (score_event(event, profile, run_id=run_id) for event in events),
        key=lambda item: (-item.scores["overall"], item.event_id),
    )
    ranked = [replace(item, rank=index) for index, item in enumerate(ranked, start=1)]
    return ranked if limit is None else ranked[:limit]
