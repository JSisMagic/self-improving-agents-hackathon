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
import threading
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from math import isfinite
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
CANONICAL_PROSPECTIVE_EVENT: dict[str, Any] = {
    "schema_version": "1.0",
    "data_mode": "live",
    "event_id": "evt_live_step_sf_20260827",
    "title": "Step SF 2026: The AI & Tech Startup Festival",
    "description": (
        "Founders, investors, builders, and operators meet for talks, live "
        "product showcases, and networking around the next wave of the AI economy."
    ),
    "source_url": "https://luma.com/StepSF26",
    "source_name": "Luma",
    "start_time": "2026-08-27T09:00:00-07:00",
    "location": "The Midway, San Francisco",
    "themes": ["AI agents", "founders"],
    "format": "conference",
    "interaction_level": 0.80,
    "knowledge_depth": 0.85,
    "estimated_crowd_size": 220,
    "cost_usd": 349,
}


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
    inspect_memory: Callable[[], Any] | None = None
    cleanup: Callable[[], None] | None = None


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
    prospective_event: Any = None
    next_events: list[Any] = field(default_factory=list)
    next_event_modes: dict[str, str] = field(default_factory=dict)
    improved_recommendations: list[Any] = field(default_factory=list)
    memory_status: dict[str, str] = field(default_factory=dict)
    memory_retrieval_evidence: list[dict[str, Any]] = field(default_factory=list)
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


def _safe_text(value: Any, *, default: str = NOT_REPORTED, limit: int = 160) -> str:
    if not isinstance(value, str) or not value.strip():
        return default
    return " ".join(value.split())[:limit]


def _safe_memory_observability(
    value: Any,
) -> tuple[dict[str, str], list[dict[str, Any]]]:
    """Normalize adapter diagnostics without adding them to shared contracts."""

    payload = _as_mapping(value)
    if not payload:
        return {}, []
    mode = _safe_action_mode(payload)
    memory_status = {
        "provider": _safe_text(payload.get("provider"), limit=64),
        "mode": mode,
        "status": _safe_status(payload),
    }
    evidence: list[dict[str, Any]] = []
    for raw_item in _items(payload.get("retrieval_evidence"))[:4]:
        item = _as_mapping(raw_item)
        try:
            relevance = float(item.get("relevance"))
        except (TypeError, ValueError):
            continue
        if not isfinite(relevance):
            continue
        storage_mode = item.get("storage_mode")
        evidence.append(
            {
                "episode_id": _safe_text(item.get("episode_id"), limit=80),
                "provider": _safe_text(item.get("provider"), limit=64),
                "relevance": round(relevance, 3),
                "storage_mode": (
                    str(storage_mode)
                    if storage_mode in {"live", "local_fallback", "fixture"}
                    else NOT_REPORTED
                ),
                "reason": _safe_text(item.get("reason")),
            }
        )
    return memory_status, evidence


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
    feedback_payload: dict[str, Any] | None,
) -> tuple[Any, list[Any], Any]:
    """Use legacy dataclasses when present; otherwise retain schema mappings."""

    try:
        from shared.contracts import Event, EventFeedback, UserProfile

        profile = UserProfile.from_dict(profile_payload)
        events = [Event.from_dict(item) for item in event_payloads]
        feedback = (
            EventFeedback.from_dict(feedback_payload)
            if feedback_payload is not None
            else None
        )
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

    from intelligence import actian_memory
    from intelligence.learning_loop import IntelligenceEngine
    from product.agents import run_agent_handoff, run_coach
    from product.band_orchestration import BandOrchestrator
    from product.event_mission import create_event_mission

    runtime_directory = tempfile.TemporaryDirectory(prefix="event-copilot-")
    memory_path = Path(runtime_directory.name) / "episodes.json"
    memory_path.write_text("[]\n", encoding="utf-8")
    create_episode_memory = getattr(
        actian_memory,
        "create_episode_memory",
        actian_memory.ActianMemory,
    )
    memory = create_episode_memory(memory_path)
    engine = IntelligenceEngine(memory)

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

    def local_handoff(profile: Any, events: list[Any], run_id: str) -> Any:
        return run_agent_handoff(profile, events, run_id=run_id)

    band_orchestrator = BandOrchestrator(local_handoff)

    def run_handoff(profile: Any, events: list[Any], run_id: str) -> Any:
        return band_orchestrator.coordinate(profile, events, run_id)

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
        from shared.contracts import Event, UserProfile

        profile_value = (
            UserProfile.from_dict(dict(profile))
            if isinstance(profile, Mapping)
            else profile
        )
        event_values = [
            Event.from_dict(dict(event)) if isinstance(event, Mapping) else event
            for event in events
        ]
        return engine.rank_events_with_memory(
            profile_value,
            event_values,
            limit=None,
            run_id="run_demo_after_v1",
        )

    def inspect_memory() -> dict[str, Any]:
        try:
            retrieval_evidence = getattr(
                memory,
                "last_retrieval_evidence",
                (),
            )
            return {
                "provider": getattr(memory, "provider", NOT_REPORTED),
                "mode": getattr(memory, "mode", "error"),
                "status": getattr(memory, "status", "unavailable"),
                "retrieval_evidence": list(retrieval_evidence),
            }
        except Exception:
            return {
                "provider": "episode_memory",
                "mode": "error",
                "status": "memory status unavailable",
                "retrieval_evidence": [],
            }

    def cleanup() -> None:
        try:
            band_orchestrator.close()
        finally:
            try:
                close_memory = getattr(memory, "close", None)
                if callable(close_memory):
                    close_memory()
            finally:
                runtime_directory.cleanup()

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
        inspect_memory=inspect_memory,
        cleanup=cleanup,
    )


class EventCopilotUI:
    """Stateful controller for WFL-001's six one-click demo actions."""

    def __init__(self, services: DemoServices | None = None) -> None:
        self.services = services or default_services()
        self.state = DemoState()
        self._closed = False
        self._refresh_memory_observability()

    def _refresh_memory_observability(self) -> None:
        inspector = self.services.inspect_memory
        if inspector is None:
            self.state.memory_status = {}
            self.state.memory_retrieval_evidence = []
            return
        try:
            raw_status = inspector()
        except Exception:
            raw_status = {
                "provider": "episode_memory",
                "mode": "error",
                "status": "memory status unavailable",
            }
        (
            self.state.memory_status,
            self.state.memory_retrieval_evidence,
        ) = _safe_memory_observability(raw_status)

    def close(self) -> None:
        """Release episode-memory resources, if this UI created them."""

        if not self._closed and self.services.cleanup is not None:
            self.services.cleanup()
        self._closed = True

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
        self._refresh_memory_observability()
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
        self.state.prospective_event = None
        self.state.next_events = []
        self.state.next_event_modes = {}
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
        self.state.prospective_event = None
        self.state.next_events = []
        self.state.next_event_modes = {}
        self.state.improved_recommendations = []
        self._refresh_memory_observability()
        return episode

    def show_improved_recommendations(
        self,
        prospective_event: Any = None,
    ) -> list[Any]:
        """TST-006: rank the next slate after a successful episode write."""

        return self.evaluate_prospective_event(
            CANONICAL_PROSPECTIVE_EVENT
            if prospective_event is None
            else prospective_event
        )

    def evaluate_prospective_event(self, event: Any) -> list[Any]:
        """Rank one new live prospect after replacing the attended candidate."""

        if self.state.episode is None:
            raise UIFlowError(
                "No successful episode write exists; save an outcome before "
                "evaluating a new prospect."
            )
        _validate_if_schema_shaped(
            event,
            "event",
            self.state.notices,
            "Prospective Event",
        )
        event_id = _event_id(event)
        if _get(event, "data_mode") != "live":
            raise UIFlowError(
                "The prospective event must use data_mode 'live' and retain its source URL."
            )

        existing_ids = {_event_id(item) for item in self.state.events}
        if event_id in existing_ids:
            raise UIFlowError(
                "The prospective event needs a new event_id; it cannot reuse an attended candidate."
            )
        source_url = str(_get(event, "source_url", "")).strip()
        existing_urls = {
            str(_get(item, "source_url", "")).strip()
            for item in self.state.events
        }
        if source_url in existing_urls:
            raise UIFlowError(
                "The prospective event needs a new source URL, not a source already ranked."
            )

        attended_event_id = _event_id(self.state.episode)
        retained_events = [
            item for item in self.state.events
            if _event_id(item) != attended_event_id
        ]
        if len(retained_events) != 2:
            raise UIFlowError(
                "The saved outcome must identify exactly one attended candidate."
            )
        prospective_events = [*retained_events, event]

        try:
            recommendations = _ordered_recommendations(
                list(self.services.rerank(self.state.profile, prospective_events))
            )
        except Exception as exc:
            raise UIFlowError(
                f"Prospective ranking failed: {exc}"
            ) from None
        if len(recommendations) != 3:
            raise UIFlowError(
                f"Prospective ranking must return three candidates; got {len(recommendations)}."
            )
        expected_ids = {_event_id(item) for item in prospective_events}
        if {_event_id(item) for item in recommendations} != expected_ids:
            raise UIFlowError(
                "Prospective ranking must contain the two retained events and the new live event."
            )

        for index, recommendation in enumerate(recommendations, start=1):
            _validate_if_schema_shaped(
                recommendation,
                "recommendation",
                self.state.notices,
                f"Prospective recommendation {index}",
            )
        self.state.prospective_event = event
        self.state.next_events = prospective_events
        self.state.next_event_modes = {
            _event_id(item): (
                "live"
                if _event_id(item) == event_id
                else self.state.event_modes.get(_event_id(item), NOT_REPORTED)
            )
            for item in prospective_events
        }
        self.state.improved_recommendations = recommendations
        self._refresh_memory_observability()
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
            "  [6] Evaluate next live event",
        ]

        if self.state.profile is not None:
            lines.extend(["", *self._render_profile(), "", *self._render_candidates()])
        if self.state.memory_status:
            lines.extend(["", *self._render_memory_status()])
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
            attended_event_id = _event_id(self.state.episode)
            attended_event = _find_by_event_id(
                self.state.events,
                attended_event_id,
            )
            prospective = self.state.prospective_event
            lines.extend(
                [
                    "",
                    "NEXT SLATE",
                    f"  Excluded attended event: {_get(attended_event, 'title', attended_event_id)}",
                    f"  Added live prospect: {_get(prospective, 'title', _event_id(prospective))}",
                    f"  Source: {_get(prospective, 'source_url', NOT_REPORTED)}",
                    "",
                    *self._render_recommendations(
                        "NEXT-EVENT RECOMMENDATIONS",
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
        band = _get(handoff, "band", {})
        band_mode = _safe_action_mode(band)
        lines = [
            "AGENT HANDOFF",
            f"  Band: {band_mode} — {_safe_status(band)}",
            f"  Scout → {_role_summary(scout, f'{len(self.state.events)} candidates')}",
            f"  Analyst → {_role_summary(analyst, f'{len(self.state.initial_recommendations)} ranked recommendations')}",
            f"  Coach → {_critique_text(critique)}",
        ]
        room_id = _get(band, "room_id")
        if isinstance(room_id, str) and room_id:
            lines.append(f"  Band room: {room_id}")
            for item in _items(_get(band, "transcript")):
                lines.append(
                    "    "
                    f"{_get(item, 'from', NOT_REPORTED)} → "
                    f"{_get(item, 'to', NOT_REPORTED)} "
                    f"[{_get(item, 'stage', NOT_REPORTED)}] "
                    f"message={_get(item, 'message_id', NOT_REPORTED)}"
                )
        return lines

    def _render_recommendations(
        self,
        title: str,
        recommendations: Sequence[Any],
        *,
        before: Sequence[Any] | None = None,
    ) -> list[str]:
        lines = [title]
        event_by_id = {
            _event_id(item): item
            for item in [*self.state.events, *self.state.next_events]
        }
        before_by_id = {
            _event_id(item): (index, item)
            for index, item in enumerate(before or [], start=1)
        }
        event_modes = (
            self.state.next_event_modes
            if before is not None and self.state.next_event_modes
            else self.state.event_modes
        )
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
                f"    Data: {event_modes.get(event_id, NOT_REPORTED)} | "
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
            elif before is not None:
                lines.append(
                    "    Delta: NEW prospective event; no prior rank or score."
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
            "  Episode write succeeded; next-slate ranking is now permitted.",
        ]

    def _render_memory_status(self) -> list[str]:
        memory = self.state.memory_status
        lines = [
            "ACTIAN MEMORY STATUS",
            "  Backend: "
            f"provider={memory.get('provider', NOT_REPORTED)} | "
            f"mode={memory.get('mode', 'error')} | "
            f"status={memory.get('status', 'unavailable')}",
        ]
        if self.state.episode is not None:
            lines.append(
                "  Write: "
                f"storage_mode={_get(self.state.episode, 'storage_mode', NOT_REPORTED)}"
            )
        if self.state.memory_retrieval_evidence:
            for item in self.state.memory_retrieval_evidence:
                relevance = item.get("relevance")
                rendered_relevance = (
                    f"{relevance:.3f}"
                    if isinstance(relevance, (int, float))
                    else NOT_REPORTED
                )
                lines.append(
                    "  Retrieval: "
                    f"episode={item.get('episode_id', NOT_REPORTED)} | "
                    f"provider={item.get('provider', NOT_REPORTED)} | "
                    f"relevance={rendered_relevance} | "
                    f"storage_mode={item.get('storage_mode', NOT_REPORTED)}"
                )
                lines.append(
                    f"    Reason: {item.get('reason', NOT_REPORTED)}"
                )
        elif self.state.improved_recommendations:
            lines.append("  Retrieval: no matching episode evidence reported.")
        return lines

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


BROWSER_HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#121713">
  <title>Event Copilot — Outcome Intelligence</title>
  <style>
    :root {
      color-scheme: dark;
      --ink: #121713;
      --ink-2: #1a211c;
      --ink-3: #273029;
      --paper: #f2f0e7;
      --muted: #9fa89f;
      --line: rgba(242, 240, 231, .13);
      --acid: #c9f66f;
      --acid-2: #9dd944;
      --warm: #ffad73;
      --blue: #84b7ff;
      --danger: #ff8e83;
      --shadow: 0 28px 70px rgba(0, 0, 0, .28);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    * { box-sizing: border-box; }
    html { scroll-behavior: smooth; }
    body {
      margin: 0;
      min-width: 320px;
      min-height: 100vh;
      color: var(--paper);
      background:
        radial-gradient(circle at 84% 10%, rgba(201, 246, 111, .13), transparent 28rem),
        radial-gradient(circle at 8% 52%, rgba(132, 183, 255, .08), transparent 24rem),
        var(--ink);
    }
    button, a { font: inherit; }
    button { color: inherit; }
    a { color: inherit; }
    .shell { width: min(1480px, calc(100% - 40px)); margin: 0 auto; }
    .topbar {
      display: flex; align-items: center; justify-content: space-between;
      min-height: 76px; border-bottom: 1px solid var(--line);
    }
    .brand { display: flex; align-items: center; gap: 12px; font-weight: 760; letter-spacing: -.02em; }
    .brand-mark {
      width: 31px; height: 31px; display: grid; place-items: center;
      color: var(--ink); background: var(--acid); border-radius: 9px;
      box-shadow: inset 0 -4px 10px rgba(18, 23, 19, .14);
    }
    .brand-mark::after { content: "EC"; font-size: 10px; letter-spacing: -.04em; font-weight: 900; }
    .truth-pill, .chip {
      display: inline-flex; align-items: center; gap: 7px; border-radius: 999px;
      border: 1px solid var(--line); background: rgba(255,255,255,.035);
      color: #c8cec8; font-size: 12px; font-weight: 700; letter-spacing: .02em;
    }
    .truth-pill { padding: 8px 11px; }
    .truth-pill::before { content: ""; width: 7px; height: 7px; border-radius: 50%; background: var(--acid); box-shadow: 0 0 0 4px rgba(201,246,111,.1); }
    .hero {
      display: grid; grid-template-columns: minmax(0, 1.35fr) minmax(280px, .65fr);
      gap: 54px; padding: 64px 0 50px; align-items: end;
    }
    .eyebrow { margin: 0 0 16px; color: var(--acid); font-size: 12px; font-weight: 850; letter-spacing: .13em; text-transform: uppercase; }
    h1 { max-width: 850px; margin: 0; font-size: clamp(48px, 6vw, 92px); line-height: .92; letter-spacing: -.065em; font-weight: 780; }
    .hero-copy { max-width: 520px; margin: 0 0 5px; color: #b8c0b9; font-size: 18px; line-height: 1.55; }
    .hero-copy strong { color: var(--paper); }
    .app-grid { display: grid; grid-template-columns: 296px minmax(0, 1fr); gap: 18px; align-items: start; padding-bottom: 72px; }
    .panel {
      border: 1px solid var(--line); border-radius: 22px;
      background: rgba(26, 33, 28, .83); box-shadow: var(--shadow);
      backdrop-filter: blur(18px);
    }
    .runbook { position: sticky; top: 18px; padding: 18px; }
    .runbook-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 18px; }
    .runbook h2, .section-head h2 { margin: 0; font-size: 15px; letter-spacing: -.02em; }
    .text-button {
      padding: 0; border: 0; color: var(--muted); background: none; cursor: pointer;
      font-size: 12px; text-decoration: underline; text-underline-offset: 3px;
    }
    .text-button:hover { color: var(--paper); }
    .steps { display: grid; gap: 7px; }
    .step {
      width: 100%; min-height: 54px; display: grid; grid-template-columns: 30px 1fr 14px;
      gap: 10px; align-items: center; padding: 9px 10px; text-align: left;
      border: 1px solid transparent; border-radius: 14px; color: #9fa89f;
      background: transparent; cursor: pointer; transition: .18s ease;
    }
    .step:hover:not(:disabled) { border-color: var(--line); color: var(--paper); background: rgba(255,255,255,.035); transform: translateX(2px); }
    .step:disabled { cursor: not-allowed; opacity: .42; }
    .step.done { color: #dfe4dc; }
    .step.current { color: var(--paper); border-color: rgba(201,246,111,.27); background: rgba(201,246,111,.08); }
    .step-number { width: 30px; height: 30px; display: grid; place-items: center; border: 1px solid var(--line); border-radius: 10px; font-size: 11px; font-weight: 800; }
    .step.done .step-number { color: var(--ink); background: var(--acid); border-color: var(--acid); }
    .step-label { font-size: 13px; font-weight: 720; line-height: 1.2; }
    .step-arrow { color: var(--acid); opacity: 0; transition: opacity .18s; }
    .step.current .step-arrow, .step:hover .step-arrow { opacity: 1; }
    .run-all {
      width: 100%; margin-top: 14px; padding: 13px 14px; border: 0; border-radius: 13px;
      color: var(--ink); background: var(--acid); font-weight: 850; cursor: pointer;
      box-shadow: inset 0 -3px 0 rgba(18,23,19,.16); transition: .18s ease;
    }
    .run-all:hover { background: #d7ff88; transform: translateY(-1px); }
    .run-all:disabled { opacity: .55; cursor: wait; }
    .mode-note { margin: 13px 2px 0; color: #778078; font-size: 11px; line-height: 1.45; }
    .workspace { min-width: 0; overflow: hidden; }
    .workspace-head {
      display: flex; align-items: center; justify-content: space-between; gap: 20px;
      padding: 20px 22px; border-bottom: 1px solid var(--line);
    }
    .workspace-title { display: flex; align-items: center; gap: 11px; }
    .workspace-title h2 { margin: 0; font-size: 15px; }
    .stage-kicker { color: var(--muted); font-size: 12px; }
    .live-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--acid); box-shadow: 0 0 0 5px rgba(201,246,111,.09); }
    .truth-row { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 7px; }
    .chip { padding: 6px 9px; }
    .chip.live, .chip.connected { color: var(--acid); border-color: rgba(201,246,111,.28); background: rgba(201,246,111,.08); }
    .chip.fixture, .chip.demo_fallback { color: var(--blue); border-color: rgba(132,183,255,.25); background: rgba(132,183,255,.07); }
    .chip.disabled { color: var(--warm); border-color: rgba(255,173,115,.25); background: rgba(255,173,115,.07); }
    .chip.error { color: var(--danger); border-color: rgba(255,142,131,.3); background: rgba(255,142,131,.08); }
    .workspace-body { padding: 22px; }
    .empty {
      min-height: 510px; display: grid; place-items: center; text-align: center;
      border-radius: 17px; border: 1px dashed rgba(242,240,231,.15);
      background: linear-gradient(145deg, rgba(255,255,255,.018), transparent);
    }
    .empty-orbit { width: 92px; height: 92px; display: grid; place-items: center; margin: 0 auto 22px; border: 1px solid rgba(201,246,111,.25); border-radius: 50%; box-shadow: inset 0 0 0 17px rgba(201,246,111,.025); }
    .empty-orbit::after { content: "01"; color: var(--acid); font-weight: 900; font-size: 25px; letter-spacing: -.04em; }
    .empty h3 { margin: 0 0 9px; font-size: 27px; letter-spacing: -.04em; }
    .empty p { max-width: 430px; margin: 0 auto 20px; color: var(--muted); line-height: 1.55; }
    .primary {
      padding: 11px 15px; border: 0; border-radius: 11px; color: var(--ink); background: var(--acid); font-weight: 820; cursor: pointer;
    }
    .stack { display: grid; gap: 18px; }
    .section { border: 1px solid var(--line); border-radius: 17px; background: rgba(255,255,255,.018); overflow: hidden; }
    .section-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 20px; padding: 17px 18px; border-bottom: 1px solid var(--line); }
    .section-head p { margin: 5px 0 0; color: var(--muted); font-size: 12px; }
    .section-body { padding: 18px; }
    .profile-grid { display: grid; grid-template-columns: 1fr 1.12fr; gap: 24px; }
    .profile-role { margin: 0 0 4px; color: var(--acid); font-size: 12px; font-weight: 800; text-transform: uppercase; letter-spacing: .08em; }
    .profile-grid h3 { margin: 0 0 12px; font-size: 25px; letter-spacing: -.035em; }
    .outcomes { display: grid; gap: 8px; margin: 18px 0 0; padding: 0; list-style: none; color: #c8cec8; font-size: 13px; }
    .outcomes li { display: grid; grid-template-columns: 18px 1fr; gap: 8px; }
    .outcomes li::before { content: "↗"; color: var(--acid); font-weight: 900; }
    .goal-list { display: grid; gap: 14px; }
    .goal-line { display: grid; grid-template-columns: 92px 1fr 42px; gap: 11px; align-items: center; font-size: 12px; font-weight: 720; text-transform: capitalize; }
    .bar { height: 8px; overflow: hidden; border-radius: 999px; background: rgba(255,255,255,.065); }
    .bar > span { display: block; height: 100%; border-radius: inherit; background: linear-gradient(90deg, var(--acid-2), var(--acid)); }
    .goal-value { text-align: right; color: var(--acid); font-variant-numeric: tabular-nums; }
    .candidate-grid, .ranking-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 11px; }
    .candidate, .rank-card { position: relative; min-width: 0; padding: 16px; border: 1px solid var(--line); border-radius: 15px; background: rgba(18,23,19,.55); }
    .candidate h3, .rank-card h3 { margin: 14px 0 7px; font-size: 16px; line-height: 1.2; letter-spacing: -.025em; }
    .candidate p { min-height: 52px; margin: 0; color: var(--muted); font-size: 12px; line-height: 1.45; }
    .meta { display: flex; flex-wrap: wrap; gap: 8px 12px; margin-top: 15px; color: #7f8980; font-size: 11px; }
    .source-link { display: inline-flex; margin-top: 13px; color: #c6d4c7; font-size: 11px; text-decoration: none; border-bottom: 1px solid rgba(198,212,199,.28); }
    .handoff { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1px; background: var(--line); }
    .agent { padding: 18px; background: var(--ink-2); }
    .agent-label { display: flex; align-items: center; gap: 8px; color: var(--acid); font-size: 11px; font-weight: 850; letter-spacing: .09em; text-transform: uppercase; }
    .agent-label::before { content: ""; width: 7px; height: 7px; border-radius: 2px; background: currentColor; }
    .agent p { margin: 10px 0 0; color: #b2bbb3; font-size: 12px; line-height: 1.5; }
    .rank-card { display: flex; flex-direction: column; transition: .18s ease; }
    .rank-card.selected { border-color: rgba(201,246,111,.55); box-shadow: inset 0 0 0 1px rgba(201,246,111,.12); }
    .rank-top { display: flex; justify-content: space-between; align-items: center; }
    .rank-number { font-size: 12px; font-weight: 900; color: var(--acid); letter-spacing: .08em; }
    .score { font-size: 28px; line-height: 1; font-weight: 850; letter-spacing: -.06em; font-variant-numeric: tabular-nums; }
    .score small { color: var(--muted); font-size: 10px; letter-spacing: 0; font-weight: 700; }
    .score-bars { display: grid; gap: 8px; margin: 14px 0; }
    .score-row { display: grid; grid-template-columns: 18px 1fr 24px; gap: 7px; align-items: center; color: #929b93; font-size: 9px; font-weight: 800; }
    .score-row .bar { height: 4px; }
    .reason { margin: 0 0 8px; color: #c3cac3; font-size: 11px; line-height: 1.45; }
    .reason::before { content: "• "; color: var(--acid); }
    .rank-footer { margin-top: auto; padding-top: 11px; border-top: 1px solid var(--line); }
    .select-button { width: 100%; padding: 9px; border: 1px solid var(--line); border-radius: 9px; color: #d9dfd8; background: rgba(255,255,255,.025); font-size: 11px; font-weight: 800; cursor: pointer; }
    .select-button:hover, .rank-card.selected .select-button { color: var(--ink); background: var(--acid); border-color: var(--acid); }
    .confidence { margin-top: 9px; color: #727c73; font-size: 10px; }
    .citation { display: block; margin-top: 8px; color: var(--blue); font-size: 10px; line-height: 1.35; text-decoration: none; }
    .mission-grid { display: grid; grid-template-columns: 1fr .85fr; gap: 18px; }
    .objective-list { display: grid; gap: 9px; }
    .objective { display: grid; grid-template-columns: 46px 1fr; gap: 12px; padding: 12px; border-radius: 12px; background: rgba(255,255,255,.028); }
    .target { display: grid; place-items: center; min-height: 42px; border-radius: 10px; color: var(--ink); background: var(--acid); font-size: 18px; font-weight: 900; }
    .objective strong { display: block; margin-bottom: 4px; font-size: 12px; }
    .objective p { margin: 0; color: var(--muted); font-size: 11px; line-height: 1.4; }
    .mini-title { margin: 18px 0 9px; color: var(--muted); font-size: 10px; font-weight: 850; letter-spacing: .1em; text-transform: uppercase; }
    .plain-list { display: grid; gap: 7px; margin: 0; padding: 0; list-style: none; color: #c6cdc6; font-size: 11px; line-height: 1.4; }
    .plain-list li { padding-left: 14px; position: relative; }
    .plain-list li::before { content: ""; position: absolute; left: 0; top: .52em; width: 5px; height: 5px; border-radius: 50%; background: var(--acid); }
    pre {
      height: 100%; max-height: 430px; margin: 0; padding: 16px; overflow: auto;
      border-radius: 13px; color: #c9d0c9; background: #0d110e; border: 1px solid rgba(255,255,255,.07);
      font: 11px/1.58 ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      white-space: pre-wrap; word-break: break-word;
    }
    .action-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 11px; }
    .action-card { padding: 15px; border: 1px solid var(--line); border-radius: 14px; background: rgba(18,23,19,.48); }
    .action-top { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
    .action-card h3 { margin: 0; font-size: 13px; }
    .action-card p { margin: 10px 0 0; color: var(--muted); font-size: 11px; line-height: 1.45; }
    .playbook { margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--line); color: #c9d0c9; font-size: 11px; line-height: 1.5; white-space: pre-wrap; }
    .learning-hero {
      display: grid; grid-template-columns: 1fr auto; gap: 24px; align-items: center;
      padding: 22px; border-radius: 15px; background: linear-gradient(115deg, rgba(201,246,111,.13), rgba(201,246,111,.03));
      border: 1px solid rgba(201,246,111,.27);
    }
    .learning-hero h3 { margin: 0 0 7px; font-size: 28px; letter-spacing: -.04em; }
    .learning-hero p { margin: 0; color: #bfc8bf; font-size: 12px; line-height: 1.5; }
    .learning-stat { text-align: right; }
    .learning-stat strong { display: block; color: var(--acid); font-size: 42px; line-height: 1; letter-spacing: -.06em; }
    .learning-stat span { color: var(--muted); font-size: 10px; text-transform: uppercase; letter-spacing: .08em; }
    .delta-table { margin-top: 14px; border: 1px solid var(--line); border-radius: 14px; overflow: hidden; }
    .delta-row { display: grid; grid-template-columns: minmax(180px, 1.4fr) .6fr .6fr .7fr; gap: 14px; align-items: center; padding: 12px 14px; border-top: 1px solid var(--line); font-size: 11px; }
    .delta-row:first-child { border-top: 0; }
    .delta-head { color: #757e76; background: rgba(255,255,255,.02); font-size: 9px; font-weight: 850; letter-spacing: .09em; text-transform: uppercase; }
    .delta-event { font-weight: 760; }
    .delta-value { font-variant-numeric: tabular-nums; }
    .positive { color: var(--acid); }
    .negative { color: var(--danger); }
    .episode { margin-top: 12px; color: #7f8980; font-size: 10px; word-break: break-all; }
    .toast {
      position: fixed; left: 50%; bottom: 24px; z-index: 10; transform: translate(-50%, 18px);
      max-width: min(520px, calc(100% - 32px)); padding: 12px 15px; border-radius: 12px;
      color: var(--paper); background: #29312b; border: 1px solid var(--line); box-shadow: var(--shadow);
      font-size: 12px; opacity: 0; pointer-events: none; transition: .22s ease;
    }
    .toast.show { opacity: 1; transform: translate(-50%, 0); }
    .toast.error { border-color: rgba(255,142,131,.35); color: #ffd2ce; }
    .loading .workspace { opacity: .72; }
    @media (max-width: 1050px) {
      .hero { grid-template-columns: 1fr; gap: 24px; }
      .hero-copy { max-width: 720px; }
      .candidate-grid, .ranking-grid { grid-template-columns: 1fr; }
      .candidate p { min-height: 0; }
      .profile-grid, .mission-grid { grid-template-columns: 1fr; }
    }
    @media (max-width: 760px) {
      .shell { width: min(100% - 22px, 1480px); }
      .topbar { min-height: 64px; }
      .truth-pill { display: none; }
      .hero { padding: 42px 0 32px; }
      h1 { font-size: clamp(44px, 16vw, 70px); }
      .hero-copy { font-size: 15px; }
      .app-grid { grid-template-columns: 1fr; }
      .runbook { position: static; }
      .steps { grid-template-columns: repeat(3, 1fr); }
      .step { min-height: 48px; grid-template-columns: 28px 1fr; }
      .step-arrow { display: none; }
      .step-label { font-size: 10px; }
      .workspace-head { align-items: flex-start; flex-direction: column; }
      .truth-row { justify-content: flex-start; }
      .workspace-body { padding: 14px; }
      .handoff { grid-template-columns: 1fr; }
      .action-grid { grid-template-columns: 1fr; }
      .learning-hero { grid-template-columns: 1fr; }
      .learning-stat { text-align: left; }
      .delta-row { grid-template-columns: minmax(140px, 1.4fr) .6fr .6fr; }
      .delta-row > :last-child { display: none; }
    }
  </style>
</head>
<body>
  <header class="shell topbar">
    <div class="brand"><span class="brand-mark" aria-hidden="true"></span>Event Copilot</div>
    <div class="truth-pill">Local learning loop</div>
  </header>
  <main class="shell">
    <section class="hero">
      <div>
        <p class="eyebrow">Outcome intelligence for intentional attendance</p>
        <h1>Choose the room that compounds.</h1>
      </div>
      <p class="hero-copy">Rank events by the outcomes you actually want, leave with a measurable mission, and let <strong>what happened</strong> improve the next recommendation.</p>
    </section>
    <section class="app-grid">
      <aside class="panel runbook" aria-label="Demo controls">
        <div class="runbook-head">
          <h2>Demo runbook</h2>
          <button class="text-button" id="resetButton" type="button">Reset</button>
        </div>
        <div class="steps" id="steps"></div>
        <button class="run-all" id="runAllButton" type="button">Run the full story</button>
        <p class="mode-note">Each episode reports the storage path actually exercised. Provider labels follow the same rule.</p>
      </aside>
      <section class="panel workspace" aria-live="polite">
        <div class="workspace-head">
          <div class="workspace-title">
            <span class="live-dot" aria-hidden="true"></span>
            <div><h2 id="stageTitle">Ready for the demo</h2><span class="stage-kicker" id="stageKicker">Six controls · one visible learning moment</span></div>
          </div>
          <div class="truth-row" id="truthRow"></div>
        </div>
        <div class="workspace-body" id="workspace"></div>
      </section>
    </section>
  </main>
  <div class="toast" id="toast" role="status"></div>
  <script>
    const controls = [
      "Load demo profile",
      "Run initial recommendation",
      "Generate Event Mission",
      "Request detailed playbook",
      "Simulate post-event feedback",
      "Evaluate next live event"
    ];
    const stageCopy = [
      ["Ready for the demo", "Six controls · one visible learning moment"],
      ["Goals and candidates loaded", "TST-001 · canonical profile and three grounded events"],
      ["Initial ranking complete", "TST-002 · Scout → Analyst → Coach"],
      ["Event Mission generated", "TST-004 · measurable objectives and exact grounded preview"],
      ["External boundaries exercised", "TST-005 · fallback and disabled modes are explicit"],
      ["Outcome recorded", "A successfully stored episode now authorizes reranking"],
      ["Next opportunity ranked", "TST-006 · attended event excluded; new live event uses prior evidence"]
    ];
    let state = null;
    let busy = false;

    const h = (value) => String(value ?? "not reported").replace(/[&<>"']/g, (char) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
    })[char]);
    const list = (value) => Array.isArray(value) ? value : [];
    const obj = (value) => value && typeof value === "object" && !Array.isArray(value) ? value : {};
    const safeUrl = (value) => {
      try {
        const parsed = new URL(String(value));
        return ["http:", "https:"].includes(parsed.protocol) ? h(parsed.href) : "#";
      } catch { return "#"; }
    };
    const eventMap = () => Object.fromEntries(list(state?.events).map((event) => [event.event_id, event]));
    const byEvent = (values, id) => list(values).find((item) => item.event_id === id);
    const actionMode = (value) => ["connected", "demo_fallback", "disabled", "error"].includes(value) ? value : "error";
    const signed = (value) => Number(value) > 0 ? `+${value}` : String(value);
    const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

    function notify(message, error = false) {
      const toast = document.getElementById("toast");
      toast.textContent = message;
      toast.className = `toast show${error ? " error" : ""}`;
      clearTimeout(notify.timer);
      notify.timer = setTimeout(() => { toast.className = "toast"; }, 2600);
    }

    async function api(path, options = {}) {
      document.body.classList.add("loading");
      try {
        const response = await fetch(path, {
          headers: { "Content-Type": "application/json" },
          ...options
        });
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.error || "The action could not be completed.");
        return payload;
      } finally {
        document.body.classList.remove("loading");
      }
    }

    async function refresh() {
      const payload = await api("/api/state");
      state = payload.state;
      render();
    }

    async function runControl(control, quiet = false) {
      if (busy) return;
      busy = true;
      renderSteps();
      try {
        const payload = await api("/api/control", {
          method: "POST",
          body: JSON.stringify({ control })
        });
        state = payload.state;
        render();
        if (!quiet) notify(`Step ${control} complete — ${controls[control - 1]}.`);
      } catch (error) {
        notify(error.message, true);
      } finally {
        busy = false;
        renderSteps();
      }
    }

    async function runAll() {
      if (busy) return;
      busy = true;
      renderSteps();
      try {
        let payload = await api("/api/reset", { method: "POST", body: "{}" });
        state = payload.state;
        render();
        for (let control = 1; control <= 6; control += 1) {
          payload = await api("/api/control", {
            method: "POST",
            body: JSON.stringify({ control })
          });
          state = payload.state;
          render();
          await sleep(260);
        }
        notify("Full story complete — the workshop now ranks first.");
      } catch (error) {
        notify(error.message, true);
      } finally {
        busy = false;
        renderSteps();
      }
    }

    async function reset() {
      if (busy) return;
      busy = true;
      try {
        const payload = await api("/api/reset", { method: "POST", body: "{}" });
        state = payload.state;
        render();
        notify("Demo reset. Session memory is clean.");
      } catch (error) {
        notify(error.message, true);
      } finally { busy = false; renderSteps(); }
    }

    async function selectEvent(eventId) {
      if (busy) return;
      busy = true;
      try {
        const payload = await api("/api/select", {
          method: "POST",
          body: JSON.stringify({ event_id: eventId })
        });
        state = payload.state;
        render();
        notify(`Selected ${eventMap()[eventId]?.title || eventId}.`);
      } catch (error) {
        notify(error.message, true);
      } finally { busy = false; renderSteps(); }
    }

    function renderSteps() {
      if (!state) return;
      const stage = Number(state.stage || 0);
      document.getElementById("steps").innerHTML = controls.map((label, index) => {
        const control = index + 1;
        const done = stage >= control;
        const current = stage + 1 === control;
        const enabled = !busy && (control === 1 || control <= stage + 1);
        return `<button class="step${done ? " done" : ""}${current ? " current" : ""}" data-control="${control}" type="button" ${enabled ? "" : "disabled"}>
          <span class="step-number">${done ? "✓" : String(control).padStart(2, "0")}</span>
          <span class="step-label">${h(label)}</span><span class="step-arrow">→</span>
        </button>`;
      }).join("");
      document.getElementById("runAllButton").disabled = busy;
    }

    function renderTruth() {
      const modes = Object.values(obj(state.event_modes));
      const fixtures = modes.filter((mode) => mode === "fixture").length;
      const live = modes.filter((mode) => mode === "live").length;
      const publication = obj(state.publication);
      const playbook = obj(state.playbook);
      const chips = [];
      if (state.stage > 0) {
        if (live) chips.push(`<span class="chip live">${live} live source</span>`);
        if (fixtures) chips.push(`<span class="chip fixture">${fixtures} fixtures</span>`);
      }
      if (state.publication) chips.push(`<span class="chip ${h(actionMode(publication.mode))}">cited.md · ${h(actionMode(publication.mode))}</span>`);
      if (state.playbook) chips.push(`<span class="chip ${h(actionMode(playbook.mode))}">x402 · ${h(actionMode(playbook.mode))}</span>`);
      document.getElementById("truthRow").innerHTML = chips.join("");
    }

    function renderProfile() {
      const profile = obj(state.profile);
      const goals = obj(profile.goal_priorities || profile.goal_weights);
      const outcomes = list(profile.desired_outcomes);
      return `<section class="section">
        <div class="section-head"><div><h2>Founder intent</h2><p>Recommendations optimize for outcomes, not registrations.</p></div><span class="chip fixture">canonical profile</span></div>
        <div class="section-body profile-grid">
          <div>
            <p class="profile-role">${h(profile.user_id)}</p>
            <h3>${h(profile.role || profile.name)}</h3>
            <ul class="outcomes">${outcomes.map((item) => `<li>${h(item)}</li>`).join("")}</ul>
          </div>
          <div class="goal-list">${["networking", "knowledge", "opportunity"].map((goal) => {
            const raw = Number(goals[goal]);
            const percent = Number.isFinite(raw) ? Math.round(raw * 100) : 0;
            return `<div class="goal-line"><span>${h(goal)}</span><span class="bar"><span style="width:${Math.max(0, Math.min(100, percent))}%"></span></span><span class="goal-value">${percent}%</span></div>`;
          }).join("")}</div>
        </div>
      </section>`;
    }

    function renderCandidates() {
      return `<section class="section">
        <div class="section-head"><div><h2>Three grounded candidates</h2><p>Two deterministic fixtures plus one live-source record.</p></div></div>
        <div class="section-body candidate-grid">${list(state.events).map((event) => `
          <article class="candidate">
            <span class="chip ${h(state.event_modes[event.event_id])}">${h(state.event_modes[event.event_id])}</span>
            <h3>${h(event.title)}</h3>
            <p>${h(event.description)}</p>
            <div class="meta"><span>${h(event.format)}</span><span>${h(event.location)}</span><span>${event.estimated_crowd_size == null ? "crowd unknown" : `${h(event.estimated_crowd_size)} people`}</span></div>
            <a class="source-link" href="${safeUrl(event.source_url)}" target="_blank" rel="noreferrer">Source · ${h(event.source_name)} ↗</a>
          </article>`).join("")}
        </div>
      </section>`;
    }

    function renderHandoff() {
      const handoff = obj(state.handoff);
      const entries = [
        ["Scout", obj(handoff.scout).summary || `${list(state.events).length} candidates grounded`],
        ["Analyst", obj(handoff.analyst).summary || `${list(state.initial_recommendations).length} recommendations ranked`],
        ["Coach", obj(state.coach).critique || obj(handoff.coach).critique || handoff.critique || "Top recommendation challenged"]
      ];
      return `<section class="section">
        <div class="section-head"><div><h2>Visible agent handoff</h2><p>One shared run ID · ${h(state.run_id)}</p></div><span class="chip demo_fallback">local orchestration</span></div>
        <div class="handoff">${entries.map(([role, summary]) => `<div class="agent"><span class="agent-label">${h(role)}</span><p>${h(summary)}</p></div>`).join("")}</div>
      </section>`;
    }

    function renderRankings(title, recommendations, before = null) {
      const events = eventMap();
      const beforeById = Object.fromEntries(list(before).map((item, index) => [item.event_id, { ...item, fallbackRank: index + 1 }]));
      return `<section class="section">
        <div class="section-head"><div><h2>${h(title)}</h2><p>Outcome scores · evidence confidence · scoring version v1</p></div><span class="chip ${before ? "connected" : "demo_fallback"}">${before ? "memory applied" : "initial pass"}</span></div>
        <div class="section-body ranking-grid">${list(recommendations).map((recommendation, index) => {
          const event = events[recommendation.event_id] || {};
          const scores = obj(recommendation.scores);
          const citation = list(recommendation.citations)[0] || {};
          const prior = beforeById[recommendation.event_id];
          const rank = recommendation.rank || index + 1;
          const priorRank = prior?.rank || prior?.fallbackRank;
          const scoreDelta = prior ? Number(scores.overall) - Number(obj(prior.scores).overall) : null;
          const selected = state.selected_event_id === recommendation.event_id;
          return `<article class="rank-card${selected ? " selected" : ""}">
            <div class="rank-top"><span class="rank-number">RANK ${h(rank)} · ${h(state.event_modes[recommendation.event_id])}${prior ? ` · ${h(priorRank)}→${h(rank)}` : ""}</span><span class="score">${h(scores.overall)}<small>/100${scoreDelta === null ? "" : ` · ${h(signed(scoreDelta))}`}</small></span></div>
            <h3>${h(event.title || recommendation.event_id)}</h3>
            <div class="score-bars">${[["N", "networking"], ["K", "knowledge"], ["O", "opportunity"], ["F", "personal_fit"]].map(([short, key]) => `<div class="score-row"><span>${short}</span><span class="bar"><span style="width:${Math.max(0, Math.min(100, Number(scores[key]) || 0))}%"></span></span><span>${h(scores[key])}</span></div>`).join("")}</div>
            ${list(recommendation.reasons).slice(0, before ? 3 : 2).map((reason) => `<p class="reason">${h(reason)}</p>`).join("")}
            ${citation.url ? `<a class="citation" href="${safeUrl(citation.url)}" target="_blank" rel="noreferrer">${h(citation.claim)} ↗</a>` : `<span class="citation">No citation reported</span>`}
            <div class="rank-footer">
              ${before ? `<div class="confidence">Influencing episodes: ${list(recommendation.influencing_episode_ids).length ? h(list(recommendation.influencing_episode_ids).join(", ")) : "none"}</div>` : `<button class="select-button" data-event-id="${h(recommendation.event_id)}" type="button">${selected ? "Selected for mission ✓" : "Select this event"}</button><div class="confidence">Confidence ${Number(recommendation.confidence || 0).toFixed(2)} · scoring ${h(recommendation.scoring_version)}</div>`}
            </div>
          </article>`;
        }).join("")}</div>
      </section>`;
    }

    function renderMission() {
      const mission = obj(state.mission);
      return `<section class="section">
        <div class="section-head"><div><h2>Measurable Event Mission</h2><p>${h(mission.mission_id)} · selected from run ${h(mission.recommendation_run_id)}</p></div><span class="chip connected">grounded preview</span></div>
        <div class="section-body mission-grid">
          <div>
            <div class="objective-list">${list(mission.objectives).map((objective) => `<div class="objective"><span class="target">${h(objective.target)}</span><div><strong>${h(String(objective.metric || "").replaceAll("_", " "))}</strong><p>${h(objective.rationale)}</p></div></div>`).join("")}</div>
            <p class="mini-title">Target people</p><ul class="plain-list">${list(mission.target_people).map((item) => `<li>${h(item)}</li>`).join("")}</ul>
            <p class="mini-title">Questions to ask</p><ul class="plain-list">${list(mission.questions_to_ask).map((item) => `<li>${h(item)}</li>`).join("")}</ul>
          </div>
          <pre aria-label="Exact grounded mission Markdown">${h(state.mission_markdown)}</pre>
        </div>
      </section>`;
    }

    function renderActions() {
      const entries = [
        ["cited.md publication", obj(state.publication)],
        ["x402 playbook", obj(state.playbook)]
      ].filter(([, value]) => Object.keys(value).length);
      if (!entries.length) return "";
      return `<section class="section">
        <div class="section-head"><div><h2>External action truth</h2><p>A preview is not a publication. Demo payment mode is not a transaction.</p></div></div>
        <div class="section-body action-grid">${entries.map(([label, result]) => {
          const mode = actionMode(result.mode);
          const playbook = result.playbook;
          return `<article class="action-card"><div class="action-top"><h3>${h(label)}</h3><span class="chip ${h(mode)}">${h(mode)}</span></div><p>Provider ${h(result.provider)} · status ${h(result.status)}</p>${result.remote_url ? `<a class="source-link" href="${safeUrl(result.remote_url)}" target="_blank" rel="noreferrer">Inspect remote result ↗</a>` : ""}${playbook ? `<div class="playbook">${h(typeof playbook === "string" ? playbook : JSON.stringify(playbook, null, 2))}</div>` : ""}</article>`;
        }).join("")}</div>
      </section>`;
    }

    function renderLearning() {
      const before = list(state.initial_recommendations);
      const after = list(state.improved_recommendations);
      if (!state.episode) return "";
      if (!after.length) return `<section class="section"><div class="section-body"><div class="learning-hero"><div><h3>Outcome recorded.</h3><p>Episode ${h(state.episode.episode_id)} was written successfully. The evidence gate is open for reranking.</p></div><div class="learning-stat"><strong>${h(state.episode.actual_event_success)}</strong><span>actual success / 100</span></div></div></div></section>`;
      const afterById = Object.fromEntries(after.map((item, index) => [item.event_id, { ...item, fallbackRank: index + 1 }]));
      const events = eventMap();
      return `<section class="section">
        <div class="section-head"><div><h2>The learning moment</h2><p>Same profile · fresh candidate slate · same scoring version · one prior episode</p></div><span class="chip connected">episode applied</span></div>
        <div class="section-body">
          <div class="learning-hero"><div><h3>Experience informs the next event.</h3><p>The attended event is excluded while its outcome evidence adjusts the fresh live prospect.</p></div><div class="learning-stat"><strong>NEW</strong><span>live prospect ranked</span></div></div>
          <div class="delta-table">
            <div class="delta-row delta-head"><span>Event</span><span>Rank</span><span>Score</span><span>Evidence</span></div>
            ${before.map((prior, index) => {
              const next = afterById[prior.event_id] || {};
              const priorRank = prior.rank || index + 1;
              const nextRank = next.rank || next.fallbackRank || "—";
              const priorScore = Number(obj(prior.scores).overall);
              const nextScore = Number(obj(next.scores).overall);
              const delta = nextScore - priorScore;
              return `<div class="delta-row"><span class="delta-event">${h(events[prior.event_id]?.title || prior.event_id)}</span><span class="delta-value ${nextRank < priorRank ? "positive" : nextRank > priorRank ? "negative" : ""}">${h(priorRank)} → ${h(nextRank)}</span><span class="delta-value ${delta > 0 ? "positive" : delta < 0 ? "negative" : ""}">${h(priorScore)} → ${h(nextScore)} (${h(signed(delta))})</span><span>${list(next.influencing_episode_ids).length ? "recorded feedback" : "baseline unchanged"}</span></div>`;
            }).join("")}
          </div>
          <p class="episode">Influencing episode · ${h(state.episode.episode_id)} · ${h(state.episode.storage_mode || "not reported")} storage</p>
        </div>
      </section>`;
    }

    function render() {
      if (!state) return;
      const stage = Number(state.stage || 0);
      document.getElementById("stageTitle").textContent = stageCopy[stage][0];
      document.getElementById("stageKicker").textContent = stageCopy[stage][1];
      renderSteps();
      renderTruth();
      const workspace = document.getElementById("workspace");
      if (!stage) {
        workspace.innerHTML = `<div class="empty"><div><div class="empty-orbit"></div><h3>Start with intent.</h3><p>Load the fictional founder profile and three grounded candidates. The demo will reveal exactly how one outcome changes the next ranking.</p><button class="primary" data-control="1" type="button">Load demo profile</button></div></div>`;
        return;
      }
      const sections = [renderProfile(), state.initial_recommendations.length ? renderHandoff() : renderCandidates()];
      if (state.initial_recommendations.length) sections.push(renderRankings("Initial recommendations", state.initial_recommendations));
      if (state.mission) sections.push(renderMission());
      sections.push(renderActions());
      if (state.episode) sections.push(renderLearning());
      if (state.improved_recommendations.length) sections.push(renderRankings("Improved recommendations", state.improved_recommendations, state.initial_recommendations));
      workspace.innerHTML = `<div class="stack">${sections.filter(Boolean).join("")}</div>`;
    }

    document.addEventListener("click", (event) => {
      const controlButton = event.target.closest("[data-control]");
      if (controlButton) runControl(Number(controlButton.dataset.control));
      const selectButton = event.target.closest("[data-event-id]");
      if (selectButton) selectEvent(selectButton.dataset.eventId);
    });
    document.getElementById("runAllButton").addEventListener("click", runAll);
    document.getElementById("resetButton").addEventListener("click", reset);
    refresh().catch((error) => notify(error.message, true));
  </script>
</body>
</html>
"""

# Keep the browser presentation in a standalone asset so the guided experience
# can evolve without changing the controller or the dependency-free HTTP layer.
BROWSER_HTML = (ROOT / "product" / "ui_browser.html").read_text(
    encoding="utf-8"
)


def _browser_value(value: Any) -> Any:
    """Convert presentation state to JSON without leaking implementation objects."""

    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {str(key): _browser_value(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_browser_value(item) for item in value]
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        return _browser_value(to_dict())
    if is_dataclass(value):
        return _browser_value(asdict(value))
    try:
        return _browser_value(vars(value))
    except (TypeError, AttributeError):
        return str(value)


def _browser_stage(state: DemoState) -> int:
    if state.improved_recommendations:
        return 6
    if state.episode is not None:
        return 5
    if state.playbook is not None:
        return 4
    if state.mission is not None:
        return 3
    if state.initial_recommendations:
        return 2
    if state.profile is not None:
        return 1
    return 0


class BrowserDemoApplication:
    """Thread-safe local HTTP presentation adapter for ``EventCopilotUI``."""

    def __init__(self, ui: EventCopilotUI) -> None:
        self.ui = ui
        self._lock = threading.RLock()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            payload = _browser_value(self.ui.state)
            payload["stage"] = _browser_stage(self.ui.state)
            return payload

    def examples(self) -> dict[str, Any]:
        """Return canonical form examples without mutating the active session."""

        with self._lock:
            profile, events, feedback = load_canonical_demo()
            return {
                "profile": _browser_value(profile),
                "events": _browser_value(events),
                "feedback": _browser_value(feedback),
                "prospective_event": _browser_value(CANONICAL_PROSPECTIVE_EVENT),
            }

    def configure(
        self,
        profile: Mapping[str, Any],
        events: Sequence[Mapping[str, Any]],
        feedback: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Validate and load user-entered profile and event form data."""

        with self._lock:
            profile_value, event_values, feedback_value = _hydrate_legacy_demo(
                dict(profile),
                [dict(event) for event in events],
                dict(feedback) if feedback is not None else None,
            )
            self.ui.load_demo_profile(
                profile_value,
                event_values,
                feedback_value,
                fixture_origin=False,
            )
            return self.snapshot()

    def run_control(self, control: int) -> dict[str, Any]:
        with self._lock:
            self.ui.run_control(control)
            return self.snapshot()

    def select_event(self, event_id: str) -> dict[str, Any]:
        with self._lock:
            self.ui.select_event(event_id)
            return self.snapshot()

    def record_feedback(self, feedback: Mapping[str, Any]) -> dict[str, Any]:
        """Validate and persist user-entered feedback for the current ranking."""

        with self._lock:
            self.ui.submit_demo_feedback(dict(feedback))
            return self.snapshot()

    def evaluate_prospect(self, event: Mapping[str, Any]) -> dict[str, Any]:
        """Validate and rank a new live event after the recorded outcome."""

        with self._lock:
            self.ui.show_improved_recommendations(dict(event))
            return self.snapshot()

    def reset(self) -> dict[str, Any]:
        with self._lock:
            self.ui.close()
            self.ui = EventCopilotUI()
            return self.snapshot()

    def close(self) -> None:
        with self._lock:
            self.ui.close()


def run_browser_server(
    ui: EventCopilotUI,
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
) -> int:
    """Serve the local browser GUI until interrupted."""

    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from urllib.parse import urlsplit

    application = BrowserDemoApplication(ui)

    class Handler(BaseHTTPRequestHandler):
        server_version = "EventCopilot/1.0"

        def _send(
            self,
            status: int,
            body: bytes,
            content_type: str,
        ) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; style-src 'unsafe-inline'; "
                "script-src 'unsafe-inline'; connect-src 'self'; "
                "img-src 'self' data:; base-uri 'none'; frame-ancestors 'none'",
            )
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def _json(self, status: int, payload: Mapping[str, Any]) -> None:
            body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            self._send(status, body, "application/json; charset=utf-8")

        def _request_json(self) -> dict[str, Any]:
            raw_length = self.headers.get("Content-Length", "0")
            try:
                length = int(raw_length)
            except ValueError:
                raise UIFlowError("Invalid request length.") from None
            if length < 0 or length > 65_536:
                raise UIFlowError("Request body is too large.")
            raw = self.rfile.read(length) if length else b"{}"
            try:
                payload = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                raise UIFlowError("Request body must be valid JSON.") from None
            if not isinstance(payload, dict):
                raise UIFlowError("Request body must be a JSON object.")
            return payload

        def do_HEAD(self) -> None:
            if urlsplit(self.path).path == "/":
                self._send(200, BROWSER_HTML.encode("utf-8"), "text/html; charset=utf-8")
                return
            self._json(404, {"error": "Not found."})

        def do_GET(self) -> None:
            path = urlsplit(self.path).path
            if path == "/":
                self._send(200, BROWSER_HTML.encode("utf-8"), "text/html; charset=utf-8")
                return
            if path == "/api/state":
                self._json(200, {"state": application.snapshot()})
                return
            if path == "/api/examples":
                self._json(200, {"examples": application.examples()})
                return
            if path == "/api/health":
                self._json(200, {"status": "ok"})
                return
            self._json(404, {"error": "Not found."})

        def do_POST(self) -> None:
            path = urlsplit(self.path).path
            try:
                payload = self._request_json()
                if path == "/api/configure":
                    profile = payload.get("profile")
                    events = payload.get("events")
                    feedback = payload.get("feedback")
                    if not isinstance(profile, Mapping):
                        raise UIFlowError("profile must be a JSON object.")
                    if not isinstance(events, list) or not all(
                        isinstance(event, Mapping) for event in events
                    ):
                        raise UIFlowError("events must be a list of JSON objects.")
                    if feedback is not None and not isinstance(feedback, Mapping):
                        raise UIFlowError("feedback must be a JSON object.")
                    state = application.configure(profile, events, feedback)
                elif path == "/api/control":
                    control = payload.get("control")
                    if isinstance(control, bool) or not isinstance(control, int):
                        raise UIFlowError("control must be an integer from 1 to 6.")
                    state = application.run_control(control)
                elif path == "/api/select":
                    event_id = payload.get("event_id")
                    if not isinstance(event_id, str) or not event_id.strip():
                        raise UIFlowError("event_id must be a non-empty string.")
                    state = application.select_event(event_id.strip())
                elif path == "/api/feedback":
                    feedback = payload.get("feedback")
                    if not isinstance(feedback, Mapping):
                        raise UIFlowError("feedback must be a JSON object.")
                    state = application.record_feedback(feedback)
                elif path == "/api/prospect":
                    event = payload.get("event")
                    if not isinstance(event, Mapping):
                        raise UIFlowError("event must be a JSON object.")
                    state = application.evaluate_prospect(event)
                elif path == "/api/reset":
                    state = application.reset()
                else:
                    self._json(404, {"error": "Not found."})
                    return
            except UIFlowError as exc:
                self._json(409, {"error": str(exc)})
                return
            except Exception:
                self._json(500, {"error": "The local demo action failed safely."})
                return
            self._json(200, {"state": state})

        def log_message(self, message: str, *args: Any) -> None:
            sys.stderr.write(
                f"[browser] {self.address_string()} - {message % args}\n"
            )

    try:
        server = ThreadingHTTPServer((host, port), Handler)
    except OSError as exc:
        application.close()
        raise UIFlowError(f"Browser server could not bind to {host}:{port}: {exc}") from None

    url = f"http://{host}:{server.server_port}/"
    sys.stdout.write(f"Event Copilot browser demo: {url}\n")
    sys.stdout.write("Press Ctrl+C to stop.\n")
    sys.stdout.flush()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
        application.close()
    return 0


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
    parser.add_argument(
        "--browser",
        action="store_true",
        help="serve the dependency-free browser GUI on the local machine",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="browser server host (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="browser server port (default: 8765)",
    )
    args = parser.parse_args(argv)
    if args.all and args.browser:
        parser.error("--all and --browser cannot be used together")
    if not 0 <= args.port <= 65535:
        parser.error("--port must be between 0 and 65535")
    ui: EventCopilotUI | None = None
    try:
        ui = EventCopilotUI()
        if args.all:
            ui.run_all()
            sys.stdout.write(ui.render())
            return 0
        if args.browser:
            return run_browser_server(ui, host=args.host, port=args.port)
        return run_terminal(ui)
    except UIFlowError as exc:
        sys.stderr.write(f"Event Copilot could not start: {exc}\n")
        return 1
    finally:
        if ui is not None:
            ui.close()


if __name__ == "__main__":
    raise SystemExit(main())
