"""Transparent baseline event scoring for the first recommendation pass."""

from __future__ import annotations

from shared.contracts import Event, Recommendation, UserProfile


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


def _clamp_score(value: float) -> int:
    return round(max(0.0, min(100.0, value)))


def _theme_match(event: Event, profile: UserProfile) -> float:
    interests = [item.casefold() for item in profile.interests]
    themes = [item.casefold() for item in event.themes]
    if not interests:
        return 0.5
    matches = sum(any(interest in theme or theme in interest for theme in themes) for interest in interests)
    return min(1.0, matches / min(2, len(interests)))


def _friction(event: Event, profile: UserProfile) -> int:
    cost_penalty = 0.0
    if event.cost_usd > profile.max_cost_usd:
        cost_penalty = min(60.0, 20 + 40 * (event.cost_usd - profile.max_cost_usd) / max(1, profile.max_cost_usd))

    crowd_penalty = 0.0
    if event.estimated_crowd_size > profile.preferred_max_crowd_size:
        excess_ratio = event.estimated_crowd_size / max(1, profile.preferred_max_crowd_size) - 1
        crowd_penalty = min(18.0, excess_ratio * 8)

    location_penalty = 0 if profile.location.casefold() in event.location.casefold() else 8
    return _clamp_score(cost_penalty + crowd_penalty + location_penalty)


def score_event(event: Event, profile: UserProfile) -> Recommendation:
    crowd_access = min(1.0, event.estimated_crowd_size / 150)
    networking = _clamp_score(
        55 * event.interaction_level
        + 30 * FORMAT_NETWORKING.get(event.format, 0.55)
        + 15 * crowd_access
    )
    knowledge = _clamp_score(
        72 * event.knowledge_depth + 28 * FORMAT_KNOWLEDGE.get(event.format, 0.60)
    )
    opportunity = _clamp_score(
        45 * event.interaction_level
        + 30 * crowd_access
        + 25 * FORMAT_OPPORTUNITY.get(event.format, 0.60)
    )
    match = _theme_match(event, profile)
    format_match = 1.0 if event.format in profile.preferred_formats else 0.35
    location_match = 1.0 if profile.location.casefold() in event.location.casefold() else 0.45
    personal_fit = _clamp_score(70 * match + 20 * format_match + 10 * location_match)
    friction = _friction(event, profile)

    component_scores = {
        "networking": networking,
        "knowledge": knowledge,
        "opportunity": opportunity,
        "personal_fit": personal_fit,
    }
    weighted = sum(component_scores[name] * profile.goal_weights[name] for name in component_scores)
    overall = _clamp_score(weighted - friction * 0.10)

    strongest = max(component_scores, key=component_scores.get)
    reasons = [
        f"The event's strongest predicted outcome is {strongest} ({component_scores[strongest]}/100).",
        f"It matches {round(match * 100)}% of the demo user's priority themes.",
    ]
    if friction >= 25:
        reasons.append(f"Cost, crowd size, or travel creates {friction}/100 friction.")

    return Recommendation(
        event_id=event.event_id,
        scores={**component_scores, "friction": friction, "overall": overall},
        reasons=reasons,
        similar_past_events=[],
        confidence=0.60,
        citations=[{"claim": event.description, "url": event.source_url}],
    )


def rank_events(events: list[Event], profile: UserProfile, limit: int | None = 3) -> list[Recommendation]:
    ranked = sorted((score_event(event, profile) for event in events), key=lambda item: item.scores["overall"], reverse=True)
    return ranked if limit is None else ranked[:limit]
