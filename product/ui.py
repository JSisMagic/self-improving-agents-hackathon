"""Event Copilot's dependency-free operator and demo interface.

The module keeps presentation state separate from the shared contracts.  It
accepts dictionaries or dataclasses, reads only fields that the UI needs, and
does not add inferred values to objects crossing a contract boundary.

Run ``python3 -m product.ui`` for the six-control terminal interface or import
``EventCopilotUI`` and inject ``DemoServices`` from another presentation layer.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence, TextIO
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
DEMO_EVENT_IDS = (
    "evt_mixer_001",
    "evt_workshop_001",
    "evt_live_swarmhack_20260724",
)
ACTION_MODES = frozenset({"connected", "demo_fallback", "disabled", "error"})
NOT_REPORTED = "not reported"


class UIFlowError(RuntimeError):
    """A safe, operator-facing error in the demo sequence."""


@dataclass(slots=True)
class DemoServices:
    """Callable boundaries consumed by the UI.

    These signatures deliberately use ``Any`` at the presentation edge so the
    UI works with plain schema dictionaries and with lightweight dataclasses.
    """

    load_demo: Callable[[], tuple[Any, list[Any], Any]]
    run_handoff: Callable[[Any, list[Any], str], Any]
    run_coach: Callable[[Any, Any, Any, str], Any]
    create_mission: Callable[[Any, Any, Any, str], Any]
    render_mission: Callable[[Any, Any], str]
    publish_markdown: Callable[[str], Any] | None
    request_playbook: Callable[[str, Any], Any] | None
    record_outcome: Callable[[Any, Any, Any, Any], Any]
    rerank: Callable[[Any, list[Any]], Sequence[Any]]


@dataclass(slots=True)
class DemoState:
    profile: Any = None
    events: list[Any] = field(default_factory=list)
    feedback_fixture: Any = None
    event_modes: dict[str, str] = field(default_factory=dict)
    run_id: str | None = None
    handoff: Any = None
    initial_recommendations: list[Any] = field(default_factory=list)
    selected_event_id: str | None = None
    coach: Any = None
    mission: Any = None
    mission_markdown: str | None = None
    publication: Any = None
    playbook: Any = None
    episode: Any = None
    improved_recommendations: list[Any] = field(default_factory=list)
    notices: list[str] = field(default_factory=list)


def _as_mapping(value: Any) -> dict[str, Any]:
    """Return a shallow mapping view without failing on optional fields."""

    if value is None:
        return {}
    if isinstance(value, Mapping):
        return dict(value)
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        converted = to_dict()
        return dict(converted) if isinstance(converted, Mapping) else {}
    if is_dataclass(value):
        converted = asdict(value)
        return dict(converted) if isinstance(converted, Mapping) else {}
    try:
        return dict(vars(value))
    except (TypeError, AttributeError):
        return {}


def _get(value: Any, key: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(key, default)
    return getattr(value, key, default)


def _items(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return list(value)
    return []


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _event_id(value: Any) -> str:
    return str(_get(value, "event_id", ""))


def _profile_user_id(value: Any) -> str:
    return str(_get(value, "user_id", ""))


def _recommendation_rank(value: Any, fallback: int) -> int:
    rank = _get(value, "rank")
    return rank if isinstance(rank, int) and rank >= 1 else fallback


def _ordered_recommendations(values: Sequence[Any]) -> list[Any]:
    recommendations = list(values)
    if recommendations and all(
        isinstance(_get(item, "rank"), int) and _get(item, "rank") >= 1
        for item in recommendations
    ):
        return sorted(recommendations, key=lambda item: _get(item, "rank"))
    return recommendations


def _find_by_event_id(values: Sequence[Any], event_id: str) -> Any:
    return next((item for item in values if _event_id(item) == event_id), None)


def _safe_action_mode(result: Any) -> str:
    mode = _get(result, "mode")
    return str(mode) if mode in ACTION_MODES else "error"


def _safe_status(result: Any) -> str:
    if _safe_action_mode(result) == "error":
        return "action failed"
    status = _get(result, "status")
    if not isinstance(status, str) or not status.strip():
        return "unavailable"
    cleaned = " ".join(status.split())
    return cleaned[:80]


def _disabled_action(provider: str, message: str) -> dict[str, str]:
    return {
        "provider": provider,
        "status": message,
        "mode": "disabled",
        "timestamp": _now(),
    }


def _failed_action(provider: str) -> dict[str, str]:
    return {
        "provider": provider,
        "status": "action failed; provider details withheld",
        "mode": "error",
        "timestamp": _now(),
    }


def _validate_if_schema_shaped(
    value: Any,
    schema_name: str,
    notices: list[str],
    label: str,
) -> None:
    """Validate versioned objects; truthfully flag legacy unversioned inputs."""

    payload = _as_mapping(value)
    if not payload:
        raise UIFlowError(f"{label} is empty.")
    if "schema_version" not in payload:
        notices.append(f"{label}: schema version {NOT_REPORTED}; not claimed as validated.")
        return

    try:
        from product.schema_validation import validate_schema

        validate_schema(payload, schema_name)
    except ImportError:
        notices.append(f"{label}: schema validator unavailable.")
    except Exception as exc:
        raise UIFlowError(f"{label} failed {schema_name} validation: {exc}") from None


def _hydrate_legacy_demo(
    profile_payload: dict[str, Any],
    event_payloads: list[dict[str, Any]],
    feedback_payload: dict[str, Any],
) -> tuple[Any, list[Any], Any]:
    """Use legacy dataclasses when present; otherwise retain schema mappings."""

    try:
        from shared.contracts import Event, EventFeedback, UserProfile

        profile = UserProfile.from_dict(profile_payload)
        events = [Event.from_dict(item) for item in event_payloads]
        feedback = EventFeedback.from_dict(feedback_payload)
        return profile, events, feedback
    except (ImportError, TypeError, ValueError):
        return profile_payload, event_payloads, feedback_payload


def load_canonical_demo() -> tuple[Any, list[Any], Any]:
    """Load the canonical local profile, three candidates, and feedback."""

    with (ROOT / "shared" / "sample_profile.json").open(encoding="utf-8") as handle:
        profile_payload = json.load(handle)
    with (ROOT / "shared" / "sample_events.json").open(encoding="utf-8") as handle:
        all_events = json.load(handle)
    with (ROOT / "shared" / "sample_feedback.json").open(encoding="utf-8") as handle:
        feedback_payload = json.load(handle)

    by_id = {str(item.get("event_id", "")): item for item in all_events}
    event_payloads = [by_id[event_id] for event_id in DEMO_EVENT_IDS if event_id in by_id]
    if len(event_payloads) != 3:
        event_payloads = list(all_events[:3])
    if len(event_payloads) != 3:
        raise UIFlowError("The canonical demo must contain exactly three candidates.")

    return _hydrate_legacy_demo(profile_payload, event_payloads, feedback_payload)


def default_services() -> DemoServices:
    """Bind the UI to the directly callable local product/core interfaces."""

    from intelligence.actian_memory import ActianMemory
    from intelligence.learning_loop import IntelligenceEngine
    from product.agents import run_agent_handoff, run_coach
    from product.event_mission import create_event_mission

    runtime_directory = tempfile.TemporaryDirectory(prefix="event-copilot-")
    memory_path = Path(runtime_directory.name) / "episodes.json"
    memory_path.write_text("[]\n", encoding="utf-8")
    engine = IntelligenceEngine(ActianMemory(memory_path))
    # Retain the temporary session store for the lifetime of these closures.
    engine._product_runtime_directory = runtime_directory

    try:
        from product.cited_publisher import (
            publish_markdown,
            render_event_mission_markdown,
        )
    except ImportError:
        publish_markdown = None
        from product.event_mission import render_event_mission_markdown

    try:
        from product.payment_endpoint import request_playbook
    except ImportError:
        request_playbook = None

    def run_handoff(profile: Any, events: list[Any], run_id: str) -> Any:
        return run_agent_handoff(profile, events, run_id=run_id)

    def coach(profile: Any, event: Any, recommendation: Any, run_id: str) -> Any:
        return run_coach(profile, event, recommendation, run_id=run_id)

    def mission(profile: Any, event: Any, recommendation: Any, run_id: str) -> Any:
        return create_event_mission(
            profile,
            event,
            recommendation,
            recommendation_run_id=run_id,
        )

    def publish(markdown: str) -> Any:
        if publish_markdown is None:
            return _disabled_action("cited.md", "publisher unavailable")
        return publish_markdown(markdown)

    def playbook(event_id: str, event_mission: Any) -> Any:
        if request_playbook is None:
            return _disabled_action("x402", "payment boundary unavailable")
        return request_playbook(
            event_id,
            event_mission,
            payments_enabled=False,
        )

    def record(profile: Any, event: Any, recommendation: Any, feedback: Any) -> Any:
        return engine.record_event_outcome(
            profile,
            event,
            feedback,
            recommendation,
        )

    def rerank(profile: Any, events: list[Any]) -> Sequence[Any]:
        return engine.rank_events_with_memory(
            profile,
            events,
            limit=None,
            run_id="run_demo_after_v1",
        )

    return DemoServices(
        load_demo=load_canonical_demo,
        run_handoff=run_handoff,
        run_coach=coach,
        create_mission=mission,
        render_mission=render_event_mission_markdown,
        publish_markdown=publish,
        request_playbook=playbook,
        record_outcome=record,
        rerank=rerank,
    )


class EventCopilotUI:
    """Stateful controller for WFL-001's six one-click demo actions."""

    def __init__(self, services: DemoServices | None = None) -> None:
        self.services = services or default_services()
        self.state = DemoState()

    def load_demo_profile(
        self,
        profile: Any = None,
        events: Sequence[Any] | None = None,
        feedback: Any = None,
        *,
        fixture_origin: bool | None = None,
    ) -> DemoState:
        """WFL-001: load the profile and exactly three grounded candidates."""

        using_canonical_fixture = profile is None and events is None and feedback is None
        if using_canonical_fixture:
            profile, loaded_events, feedback = self.services.load_demo()
            events = loaded_events
        if profile is None or events is None:
            raise UIFlowError("Profile and candidates must be supplied together.")

        candidate_events = list(events)
        if len(candidate_events) != 3:
            raise UIFlowError(
                f"The hackathon demo requires exactly three candidates; got {len(candidate_events)}."
            )
        if len({_event_id(item) for item in candidate_events}) != 3 or any(
            not _event_id(item) for item in candidate_events
        ):
            raise UIFlowError("Each demo candidate must have a distinct event_id.")

        notices: list[str] = []
        _validate_if_schema_shaped(profile, "profile", notices, "Profile")
        for index, event in enumerate(candidate_events, start=1):
            _validate_if_schema_shaped(event, "event", notices, f"Event {index}")

        if fixture_origin is None:
            fixture_origin = using_canonical_fixture
        modes: dict[str, str] = {}
        for event in candidate_events:
            reported = _get(event, "data_mode")
            if reported in {"live", "fixture"}:
                modes[_event_id(event)] = str(reported)
            elif fixture_origin:
                modes[_event_id(event)] = "fixture"
            else:
                modes[_event_id(event)] = NOT_REPORTED

        self.state = DemoState(
            profile=profile,
            events=candidate_events,
            feedback_fixture=feedback,
            event_modes=modes,
            notices=notices,
        )
        return self.state

    def run_initial_recommendation(self) -> list[Any]:
        """WFL-002..004: show Scout, Analyst, and top-choice critique."""

        self._require_loaded()
        run_id = f"run_{uuid4().hex[:12]}"
        try:
            handoff = self.services.run_handoff(
                self.state.profile,
                self.state.events,
                run_id,
            )
        except Exception as exc:
            raise UIFlowError(f"Initial recommendation failed: {exc}") from None

        recommendations = _ordered_recommendations(
            _items(_get(handoff, "recommendations"))
        )
        if len(recommendations) != 3:
            raise UIFlowError(
                f"Analyst must return three recommendations; got {len(recommendations)}."
            )

        event_ids = {_event_id(item) for item in self.state.events}
        if {_event_id(item) for item in recommendations} != event_ids:
            raise UIFlowError("Recommendations must match the three loaded candidates.")

        for index, recommendation in enumerate(recommendations, start=1):
            _validate_if_schema_shaped(
                recommendation,
                "recommendation",
                self.state.notices,
                f"Recommendation {index}",
            )

        self.state.run_id = str(_get(handoff, "run_id", run_id))
        self.state.handoff = handoff
        self.state.initial_recommendations = recommendations
        self.state.selected_event_id = None
        self.state.coach = _get(handoff, "coach")
        self.state.mission = None
        self.state.mission_markdown = None
        self.state.publication = None
        self.state.playbook = None
        self.state.episode = None
        self.state.improved_recommendations = []
        return recommendations

    def select_event(self, event_id: str) -> Any:
        """Select one of the three ranked candidates for mission generation."""

        self._require_initial_ranking()
        event = _find_by_event_id(self.state.events, event_id)
        if event is None:
            raise UIFlowError(f"Unknown event_id {event_id!r}.")
        self.state.selected_event_id = event_id
        return event

    def generate_event_mission(self, *, attempt_publish: bool = True) -> Any:
        """WFL-005: create, render, and optionally publish the exact mission."""

        self._require_initial_ranking()
        if not self.state.selected_event_id:
            raise UIFlowError("Select an event before generating its mission.")

        event = _find_by_event_id(self.state.events, self.state.selected_event_id)
        recommendation = _find_by_event_id(
            self.state.initial_recommendations,
            self.state.selected_event_id,
        )
        if event is None or recommendation is None:
            raise UIFlowError("The selected event is not in the current ranking.")

        try:
            coach = self.services.run_coach(
                self.state.profile,
                event,
                recommendation,
                self.state.run_id or "",
            )
            mission = _get(coach, "mission")
            if mission is None:
                mission = self.services.create_mission(
                    self.state.profile,
                    event,
                    recommendation,
                    self.state.run_id or "",
                )
            markdown = self.services.render_mission(mission, event)
        except Exception as exc:
            raise UIFlowError(f"Mission generation failed: {exc}") from None

        _validate_if_schema_shaped(
            mission,
            "mission",
            self.state.notices,
            "Event Mission",
        )
        if not isinstance(markdown, str) or not markdown.strip():
            raise UIFlowError("Mission renderer returned an empty preview.")

        self.state.coach = coach
        self.state.mission = mission
        self.state.mission_markdown = markdown
        if attempt_publish:
            if self.services.publish_markdown is None:
                self.state.publication = _disabled_action(
                    "cited.md",
                    "publisher disabled",
                )
            else:
                try:
                    self.state.publication = self.services.publish_markdown(markdown)
                except Exception:
                    self.state.publication = _failed_action("cited.md")
        return mission

    def request_detailed_playbook(self) -> Any:
        """WFL-006: request the playbook through the x402 boundary."""

        if self.state.mission is None or not self.state.selected_event_id:
            raise UIFlowError("Generate an Event Mission before requesting its playbook.")
        if self.services.request_playbook is None:
            result = _disabled_action("x402", "payment boundary disabled")
        else:
            try:
                result = self.services.request_playbook(
                    self.state.selected_event_id,
                    self.state.mission,
                )
            except Exception:
                result = _failed_action("x402")
        self.state.playbook = result
        return result

    def submit_demo_feedback(self, feedback: Any = None) -> Any:
        """WFL-007: validate and persist feedback without claiming reranking yet."""

        self._require_initial_ranking()
        feedback = self.state.feedback_fixture if feedback is None else feedback
        if feedback is None:
            raise UIFlowError("No feedback was supplied.")

        _validate_if_schema_shaped(
            feedback,
            "feedback",
            self.state.notices,
            "Event Feedback",
        )
        feedback_event_id = _event_id(feedback)
        event = _find_by_event_id(self.state.events, feedback_event_id)
        recommendation = _find_by_event_id(
            self.state.initial_recommendations,
            feedback_event_id,
        )
        if event is None or recommendation is None:
            raise UIFlowError("Feedback event_id must match one of the ranked candidates.")

        try:
            episode = self.services.record_outcome(
                self.state.profile,
                event,
                recommendation,
                feedback,
            )
        except Exception as exc:
            self.state.episode = None
            self.state.improved_recommendations = []
            raise UIFlowError(
                f"Feedback was not recorded; learning did not occur: {exc}"
            ) from None

        _validate_if_schema_shaped(
            episode,
            "episode",
            self.state.notices,
            "Event Episode",
        )
        self.state.episode = episode
        self.state.improved_recommendations = []
        return episode

    def show_improved_recommendations(self) -> list[Any]:
        """TST-006: rerank only after a successful episode write."""

        if self.state.episode is None:
            raise UIFlowError(
                "No successful episode write exists; improved rankings are unavailable."
            )
        try:
            recommendations = _ordered_recommendations(
                list(self.services.rerank(self.state.profile, self.state.events))
            )
        except Exception as exc:
            raise UIFlowError(f"Reranking failed: {exc}") from None
        if len(recommendations) != 3:
            raise UIFlowError(
                f"Reranking must return the same three candidates; got {len(recommendations)}."
            )
        if {_event_id(item) for item in recommendations} != {
            _event_id(item) for item in self.state.events
        }:
            raise UIFlowError("Reranking changed the candidate set.")

        for index, recommendation in enumerate(recommendations, start=1):
            _validate_if_schema_shaped(
                recommendation,
                "recommendation",
                self.state.notices,
                f"Improved recommendation {index}",
            )
        self.state.improved_recommendations = recommendations
        return recommendations

    def run_control(self, control: int) -> Any:
        """Dispatch one of WFL-001's six stage-friendly controls."""

        if control == 1:
            return self.load_demo_profile()
        if control == 2:
            return self.run_initial_recommendation()
        if control == 3:
            if not self.state.selected_event_id:
                self._require_initial_ranking()
                self.select_event(_event_id(self.state.initial_recommendations[0]))
            return self.generate_event_mission()
        if control == 4:
            return self.request_detailed_playbook()
        if control == 5:
            return self.submit_demo_feedback()
        if control == 6:
            return self.show_improved_recommendations()
        raise UIFlowError(f"Unknown control {control!r}.")

    def run_all(self) -> DemoState:
        """Execute the complete local journey in the documented control order."""

        for control in range(1, 7):
            self.run_control(control)
        return self.state

    def render(self) -> str:
        """Render the current single-screen state without side effects."""

        lines = [
            "EVENT COPILOT",
            "Choose events by measured outcomes, then learn from what happened.",
            "",
            "DEMO CONTROLS",
            "  [1] Load demo profile",
            "  [2] Run initial recommendation",
            "  [3] Generate Event Mission",
            "  [4] Request detailed playbook",
            "  [5] Simulate post-event feedback",
            "  [6] Show improved recommendations",
        ]

        if self.state.profile is not None:
            lines.extend(["", *self._render_profile(), "", *self._render_candidates()])
        if self.state.initial_recommendations:
            lines.extend(
                [
                    "",
                    *self._render_handoff(),
                    "",
                    *self._render_recommendations(
                        "INITIAL RECOMMENDATIONS",
                        self.state.initial_recommendations,
                    ),
                ]
            )
        if self.state.selected_event_id:
            event = _find_by_event_id(self.state.events, self.state.selected_event_id)
            lines.extend(
                [
                    "",
                    f"SELECTED EVENT: {_get(event, 'title', self.state.selected_event_id)}",
                ]
            )
        if self.state.mission_markdown:
            lines.extend(
                [
                    "",
                    "EXACT GROUNDED MISSION PREVIEW",
                    self.state.mission_markdown.rstrip(),
                ]
            )
        if self.state.publication is not None or self.state.playbook is not None:
            lines.extend(["", "EXTERNAL ACTION STATUS"])
            if self.state.publication is not None:
                lines.extend(self._render_action("Publication", self.state.publication))
            if self.state.playbook is not None:
                lines.extend(self._render_action("Playbook", self.state.playbook))
        if self.state.episode is not None:
            lines.extend(["", *self._render_episode()])
        if self.state.improved_recommendations:
            lines.extend(
                [
                    "",
                    *self._render_recommendations(
                        "IMPROVED RECOMMENDATIONS",
                        self.state.improved_recommendations,
                        before=self.state.initial_recommendations,
                    ),
                ]
            )
        if self.state.notices:
            lines.extend(["", "CONTRACT NOTICES"])
            lines.extend(f"  - {notice}" for notice in dict.fromkeys(self.state.notices))

        return "\n".join(lines).rstrip() + "\n"

    def _render_profile(self) -> list[str]:
        profile = self.state.profile
        priorities = _get(profile, "goal_priorities")
        if not isinstance(priorities, Mapping):
            priorities = _get(profile, "goal_weights", {})
        role = _get(profile, "role", _get(profile, "name", NOT_REPORTED))
        lines = [
            "DEMO PROFILE",
            f"  User: {_profile_user_id(profile) or NOT_REPORTED}",
            f"  Role: {role}",
            "  Goal priorities:",
        ]
        for goal in ("networking", "knowledge", "opportunity"):
            value = priorities.get(goal) if isinstance(priorities, Mapping) else None
            rendered = f"{float(value):.0%}" if isinstance(value, (int, float)) else NOT_REPORTED
            lines.append(f"    - {goal}: {rendered}")

        outcomes = _items(_get(profile, "desired_outcomes"))
        if outcomes:
            lines.append("  Desired outcomes:")
            lines.extend(f"    - {item}" for item in outcomes)
        return lines

    def _render_candidates(self) -> list[str]:
        lines = ["THREE GROUNDED CANDIDATES"]
        for event in self.state.events:
            event_id = _event_id(event)
            lines.extend(
                [
                    f"  - {_get(event, 'title', event_id)} [{self.state.event_modes.get(event_id, NOT_REPORTED)}]",
                    f"    Format: {_get(event, 'format', NOT_REPORTED)}",
                    f"    Source: {_get(event, 'source_name', NOT_REPORTED)} — {_get(event, 'source_url', NOT_REPORTED)}",
                ]
            )
        return lines

    def _render_handoff(self) -> list[str]:
        handoff = self.state.handoff
        scout = _get(handoff, "scout")
        analyst = _get(handoff, "analyst")
        coach = _get(handoff, "coach")
        critique = _get(handoff, "critique", _get(coach, "critique"))
        return [
            "AGENT HANDOFF",
            f"  Scout → {_role_summary(scout, f'{len(self.state.events)} candidates')}",
            f"  Analyst → {_role_summary(analyst, f'{len(self.state.initial_recommendations)} ranked recommendations')}",
            f"  Coach → {_critique_text(critique)}",
        ]

    def _render_recommendations(
        self,
        title: str,
        recommendations: Sequence[Any],
        *,
        before: Sequence[Any] | None = None,
    ) -> list[str]:
        lines = [title]
        event_by_id = {_event_id(item): item for item in self.state.events}
        before_by_id = {
            _event_id(item): (index, item)
            for index, item in enumerate(before or [], start=1)
        }
        for index, recommendation in enumerate(recommendations, start=1):
            event_id = _event_id(recommendation)
            event = event_by_id.get(event_id)
            rank = _recommendation_rank(recommendation, index)
            scores = _get(recommendation, "scores", {})
            if not isinstance(scores, Mapping):
                scores = {}
            lines.append(
                f"  #{rank} {_get(event, 'title', event_id)} — {scores.get('overall', NOT_REPORTED)}/100"
            )
            lines.append(
                f"    Data: {self.state.event_modes.get(event_id, NOT_REPORTED)} | "
                f"Confidence: {_confidence_text(_get(recommendation, 'confidence'))} | "
                f"Scoring: {_get(recommendation, 'scoring_version', NOT_REPORTED)}"
            )
            component_names = (
                "networking",
                "knowledge",
                "opportunity",
                "personal_fit",
                "friction",
            )
            components = " | ".join(
                f"{name} {scores.get(name, NOT_REPORTED)}" for name in component_names
            )
            lines.append(f"    Scores: {components}")

            if event_id in before_by_id:
                before_index, before_item = before_by_id[event_id]
                before_rank = _recommendation_rank(before_item, before_index)
                before_scores = _get(before_item, "scores", {})
                before_overall = (
                    before_scores.get("overall")
                    if isinstance(before_scores, Mapping)
                    else None
                )
                after_overall = scores.get("overall")
                lines.append(
                    f"    Delta: rank {before_rank} → {rank}"
                    f"{_score_delta(before_overall, after_overall)}"
                )

            reasons = _items(_get(recommendation, "reasons"))
            for reason in reasons:
                lines.append(f"    Reason: {reason}")

            adjustments = _items(_get(recommendation, "adjustments"))
            for adjustment in adjustments:
                lines.append(
                    "    Evidence adjustment: "
                    f"{_get(adjustment, 'component', NOT_REPORTED)} "
                    f"{_signed(_get(adjustment, 'delta'))} — "
                    f"{_get(adjustment, 'evidence_summary', NOT_REPORTED)}"
                )

            episode_ids = _items(_get(recommendation, "influencing_episode_ids"))
            if not episode_ids:
                episode_ids = _items(_get(recommendation, "similar_past_events"))
            lines.append(
                "    Influencing episodes: "
                + (", ".join(str(item) for item in episode_ids) if episode_ids else "none")
            )

            citations = _items(_get(recommendation, "citations"))
            if citations:
                for citation in citations:
                    lines.append(
                        f"    Citation: {_get(citation, 'claim', NOT_REPORTED)} — "
                        f"{_get(citation, 'url', NOT_REPORTED)}"
                    )
            else:
                lines.append("    Citation: none reported")
        return lines

    def _render_action(self, label: str, result: Any) -> list[str]:
        provider = _get(result, "provider", NOT_REPORTED)
        lines = [
            f"  {label}: provider={provider} | mode={_safe_action_mode(result)} | "
            f"status={_safe_status(result)}"
        ]
        remote_id = _get(result, "remote_id")
        remote_url = _get(result, "remote_url")
        if remote_id:
            lines.append(f"    Remote ID: {remote_id}")
        if remote_url:
            lines.append(f"    Remote URL: {remote_url}")

        payment_mode = _get(result, "payment_mode")
        if payment_mode:
            lines.append(f"    Payment mode: {payment_mode}")
        payment = _get(result, "payment")
        if isinstance(payment, Mapping):
            for key in (
                "network",
                "request_id",
                "verification_id",
                "transaction_id",
                "payment_url",
                "receipt_url",
                "amount",
                "currency",
            ):
                if payment.get(key) is not None:
                    lines.append(f"    {key.replace('_', ' ').title()}: {payment[key]}")

        playbook = _get(result, "playbook")
        if isinstance(playbook, str) and playbook.strip():
            lines.extend(["    Detailed playbook:", *[f"      {line}" for line in playbook.splitlines()]])
        elif isinstance(playbook, Mapping):
            lines.append("    Detailed playbook:")
            for key in (
                "event_id",
                "target_people",
                "questions",
                "objectives",
                "follow_up_strategy",
            ):
                value = playbook.get(key)
                if value is None:
                    continue
                label_text = key.replace("_", " ").title()
                if isinstance(value, list):
                    lines.append(f"      {label_text}:")
                    for item in value:
                        if isinstance(item, Mapping):
                            metric = item.get("metric", NOT_REPORTED)
                            target = item.get("target", NOT_REPORTED)
                            rationale = item.get("rationale", NOT_REPORTED)
                            lines.append(
                                f"        - {metric}: target {target} — {rationale}"
                            )
                        else:
                            lines.append(f"        - {item}")
                else:
                    lines.append(f"      {label_text}: {value}")

        if _safe_action_mode(result) == "error":
            lines.append("    Error details are withheld from the interface.")
        return lines

    def _render_episode(self) -> list[str]:
        episode_id = _get(self.state.episode, "episode_id", NOT_REPORTED)
        actual_success = _get(
            self.state.episode,
            "actual_event_success",
            NOT_REPORTED,
        )
        storage_mode = _get(
            self.state.episode,
            "storage_mode",
            NOT_REPORTED,
        )
        return [
            "LEARNING RECORD",
            f"  Episode: {episode_id}",
            f"  Actual event success: {actual_success}/100",
            f"  Storage mode: {storage_mode}",
            "  Episode write succeeded; reranking is now permitted.",
        ]

    def _require_loaded(self) -> None:
        if self.state.profile is None or len(self.state.events) != 3:
            raise UIFlowError("Load the demo profile before continuing.")

    def _require_initial_ranking(self) -> None:
        self._require_loaded()
        if len(self.state.initial_recommendations) != 3:
            raise UIFlowError("Run the initial recommendation before continuing.")


def _role_summary(role_result: Any, fallback: str) -> str:
    if role_result is None:
        return fallback
    for key in ("summary", "message", "status"):
        value = _get(role_result, key)
        if isinstance(value, str) and value.strip():
            return " ".join(value.split())
    return fallback


def _critique_text(critique: Any) -> str:
    if isinstance(critique, str) and critique.strip():
        return " ".join(critique.split())
    if isinstance(critique, Mapping):
        for key in ("risk", "weakness", "summary", "message"):
            value = critique.get(key)
            if isinstance(value, str) and value.strip():
                return " ".join(value.split())
    return NOT_REPORTED


def _confidence_text(value: Any) -> str:
    if isinstance(value, (int, float)) and 0 <= value <= 1:
        return f"{value:.2f} (evidence confidence; not a calibrated probability)"
    return NOT_REPORTED


def _score_delta(before: Any, after: Any) -> str:
    if isinstance(before, (int, float)) and isinstance(after, (int, float)):
        return f" | score {before} → {after} ({after - before:+g})"
    return f" | score delta {NOT_REPORTED}"


def _signed(value: Any) -> str:
    if isinstance(value, (int, float)):
        return f"{value:+g}"
    return NOT_REPORTED


def run_terminal(
    ui: EventCopilotUI,
    *,
    input_stream: TextIO = sys.stdin,
    output_stream: TextIO = sys.stdout,
) -> int:
    """Run the operator menu; errors stay safe and the local flow stays usable."""

    output_stream.write(ui.render())
    while True:
        output_stream.write("\nChoose 1-6, [a] run all, or [q] quit: ")
        output_stream.flush()
        choice = input_stream.readline()
        if not choice:
            return 0
        choice = choice.strip().casefold()
        if choice in {"q", "quit", "exit"}:
            return 0
        try:
            if choice in {"a", "all"}:
                ui.run_all()
            else:
                ui.run_control(int(choice))
        except (ValueError, UIFlowError) as exc:
            output_stream.write(f"\nACTION NOT COMPLETED: {exc}\n")
        output_stream.write("\n" + ui.render())


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Event Copilot demo interface.")
    parser.add_argument(
        "--all",
        action="store_true",
        help="run all six controls once, print the resulting screen, and exit",
    )
    args = parser.parse_args(argv)
    try:
        ui = EventCopilotUI()
        if args.all:
            ui.run_all()
            sys.stdout.write(ui.render())
            return 0
        return run_terminal(ui)
    except UIFlowError as exc:
        sys.stderr.write(f"Event Copilot could not start: {exc}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
