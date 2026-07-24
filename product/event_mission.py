"""Grounded, deterministic Event Mission generation.

The functions in this module deliberately accept either shared dataclass
instances or mapping-shaped boundary objects.  The returned mission is a plain
dictionary containing exactly the fields defined by ``mission.schema.json``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any
from urllib.parse import urlparse


Record = Mapping[str, Any] | object


def _as_mapping(value: Record, label: str) -> dict[str, Any]:
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


def _required_text(record: Mapping[str, Any], field: str, label: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label}.{field} must be a non-empty string")
    return value.strip()


def _score(recommendation: Mapping[str, Any], component: str) -> float:
    scores = recommendation.get("scores")
    if not isinstance(scores, Mapping):
        return 0.0
    value = scores.get(component, 0)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0.0
    return max(0.0, min(100.0, float(value)))


def _is_grounded_url(value: object) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _citations(
    event: Mapping[str, Any],
    recommendation: Mapping[str, Any],
) -> list[dict[str, str]]:
    """Preserve claim-level recommendation and normalized-event grounding."""

    result: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    candidates = recommendation.get("citations", [])
    if isinstance(candidates, Sequence) and not isinstance(candidates, (str, bytes)):
        for item in candidates:
            if not isinstance(item, Mapping):
                continue
            claim = item.get("claim")
            url = item.get("url")
            if not isinstance(claim, str) or not claim.strip() or not _is_grounded_url(url):
                continue
            pair = (claim.strip(), str(url))
            if pair not in seen:
                seen.add(pair)
                result.append({"claim": pair[0], "url": pair[1]})

    source_url = event.get("source_url")
    description = event.get("description")
    if _is_grounded_url(source_url) and isinstance(description, str) and description.strip():
        event_pair = (description.strip(), str(source_url))
        if event_pair not in seen:
            result.append({"claim": event_pair[0], "url": event_pair[1]})

    if not result:
        raise ValueError(
            "Event Mission requires at least one claim-level citation from the "
            "recommendation or normalized event"
        )
    return result


def _target_roles(event: Mapping[str, Any]) -> list[str]:
    themes = event.get("themes", [])
    if not isinstance(themes, Sequence) or isinstance(themes, (str, bytes)):
        themes = []

    roles: list[str] = []
    for theme_value in themes:
        theme = str(theme_value).strip()
        lowered = theme.casefold()
        if not theme:
            continue
        if "cto" in lowered or "engineering leadership" in lowered:
            role = "CTOs and engineering leaders"
        elif "founder" in lowered:
            role = "AI founders and startup operators"
        elif "agent" in lowered:
            role = "Agent builders and practitioners"
        else:
            # Themes are not an attendee roster. Keep unknown values generic so
            # a name-like theme can never become an implied access promise.
            role = "Practitioners working on the event's other listed themes"
        if role not in roles:
            roles.append(role)
        if len(roles) == 2:
            break

    if not roles:
        event_format = str(event.get("format") or "event").strip()
        roles.append(f"Participants active in the {event_format} sessions")
    return roles


def _created_at(value: str | datetime | None) -> str:
    if value is None:
        return datetime.now(timezone.utc).isoformat()
    if isinstance(value, datetime):
        timestamp = value
    elif isinstance(value, str):
        normalized = value.strip().replace("Z", "+00:00")
        try:
            timestamp = datetime.fromisoformat(normalized)
        except ValueError as exc:
            raise ValueError("created_at must be an ISO 8601 date-time") from exc
    else:
        raise TypeError("created_at must be a datetime, ISO 8601 string, or None")

    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return timestamp.isoformat()


def create_event_mission(
    profile: Record,
    event: Record,
    recommendation: Record,
    *,
    recommendation_run_id: str | None = None,
    created_at: str | datetime | None = None,
) -> dict[str, Any]:
    """Create a measurable, grounded Event Mission.

    ``recommendation_run_id`` takes precedence over a ``run_id`` embedded in
    the recommendation.  Legacy recommendations without run provenance must
    therefore be given the caller's run ID explicitly.
    """

    profile_data = _as_mapping(profile, "profile")
    event_data = _as_mapping(event, "event")
    recommendation_data = _as_mapping(recommendation, "recommendation")

    user_id = _required_text(profile_data, "user_id", "profile")
    event_id = _required_text(event_data, "event_id", "event")
    event_title = _required_text(event_data, "title", "event")
    recommended_event_id = _required_text(
        recommendation_data, "event_id", "recommendation"
    )
    if recommended_event_id != event_id:
        raise ValueError("recommendation.event_id must match event.event_id")

    run_id_value = recommendation_run_id or recommendation_data.get("run_id")
    if not isinstance(run_id_value, str) or not run_id_value.strip():
        raise ValueError(
            "recommendation_run_id is required when the recommendation has no run_id"
        )
    run_id = run_id_value.strip()

    networking_target = 3 if _score(recommendation_data, "networking") >= 75 else 2
    knowledge_target = 2 if _score(recommendation_data, "knowledge") >= 75 else 1
    follow_up_target = 2 if _score(recommendation_data, "opportunity") >= 75 else 1

    identity = f"{user_id}|{event_id}|{run_id}".encode("utf-8")
    mission_id = f"mission_{sha256(identity).hexdigest()[:12]}"

    mission = {
        "schema_version": "1.0",
        "mission_id": mission_id,
        "user_id": user_id,
        "event_id": event_id,
        "recommendation_run_id": run_id,
        "objectives": [
            {
                "metric": "meaningful_conversations",
                "target": networking_target,
                "rationale": (
                    f"Use {event_title} to test the recommendation's predicted "
                    "networking value with an observable conversation count."
                ),
            },
            {
                "metric": "questions_answered",
                "target": knowledge_target,
                "rationale": (
                    "Capture concrete answers that can be compared with "
                    "post-event knowledge feedback."
                ),
            },
            {
                "metric": "followups_sent",
                "target": follow_up_target,
                "rationale": (
                    "Convert useful conversations into a measurable next step "
                    "instead of treating attendance as success."
                ),
            },
        ],
        "target_people": _target_roles(event_data),
        "questions_to_ask": [
            "What evidence shows that your agent or AI workflow improves after feedback?",
            "Which implementation constraint most often blocks a reliable production rollout?",
            "What concrete next step would make a follow-up useful to both of us?",
        ],
        "follow_up_plan": (
            "Within 24 hours, send concise notes to the most relevant contacts; "
            f"within 72 hours, complete at least {follow_up_target} follow-up "
            "action(s) and record meetings or opportunities created."
        ),
        "citations": _citations(event_data, recommendation_data),
        "created_at": _created_at(created_at),
    }
    # Validate at the product boundary without introducing a second model.
    from shared import EventMission

    return EventMission.from_dict(mission).to_dict()


def render_event_mission_markdown(
    mission: Mapping[str, Any],
    event: Record | None = None,
) -> str:
    """Render the exact mission data as citation-bearing Markdown."""

    event_title = "Selected event"
    if event is not None:
        event_data = _as_mapping(event, "event")
        event_title = _required_text(event_data, "title", "event")

    lines = [
        f"# Event Mission: {event_title}",
        "",
        f"- Mission ID: `{mission['mission_id']}`",
        f"- Recommendation run: `{mission['recommendation_run_id']}`",
        f"- Event ID: `{mission['event_id']}`",
        "",
        "## Measurable objectives",
        "",
    ]
    for objective in mission["objectives"]:
        lines.append(
            f"- **{objective['metric']} — target {objective['target']:g}:** "
            f"{objective['rationale']}"
        )

    lines.extend(["", "## Target people or roles", ""])
    lines.extend(f"- {target}" for target in mission["target_people"])
    lines.extend(["", "## Questions to ask", ""])
    lines.extend(f"- {question}" for question in mission["questions_to_ask"])
    lines.extend(
        [
            "",
            "## Follow-up plan",
            "",
            str(mission["follow_up_plan"]),
            "",
            "## Sources",
            "",
        ]
    )
    for index, citation in enumerate(mission["citations"], start=1):
        lines.append(f"- [{index}] [{citation['claim']}]({citation['url']})")
    return "\n".join(lines) + "\n"
