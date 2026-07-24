"""Fast local loop: validate feedback, write one episode, and rerank."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import os
from pathlib import Path
from statistics import fmean
import tempfile
from typing import Any
from uuid import uuid4

from shared.contracts import (
    SCHEMA_VERSION,
    SCORING_VERSION,
    Event,
    EventEpisode,
    EventFeedback,
    Recommendation,
    UserProfile,
)

from .actian_memory import EpisodeMemory, create_episode_memory
from .scorer import overall_score, rank_events, score_event


def clamp(value: float) -> int:
    return round(max(0.0, min(100.0, value)))


def feedback_outcome_scores(feedback: EventFeedback) -> dict[str, int]:
    """Apply the accepted MET-001 deterministic component normalizers."""

    return {
        "networking": clamp(
            10
            * (
                feedback.meaningful_conversations
                + feedback.contacts_exchanged
                + 2 * feedback.meetings_booked
            )
        ),
        "knowledge": clamp(
            15 * feedback.questions_answered
            + 20 * feedback.actionable_insights
        ),
        "opportunity": clamp(
            20 * feedback.followups_sent
            + 40 * feedback.opportunities_created
        ),
        "personal_fit": clamp(
            5 * feedback.energy_after + 5 * feedback.overall_value
        ),
    }


def actual_event_success(actual_scores: dict[str, float]) -> int:
    return clamp(
        0.30 * actual_scores["networking"]
        + 0.30 * actual_scores["knowledge"]
        + 0.30 * actual_scores["opportunity"]
        + 0.10 * actual_scores["personal_fit"]
    )


class IntelligenceEngine:
    def __init__(self, memory: EpisodeMemory) -> None:
        self.memory = memory

    def retrieve_similar_experiences(
        self,
        user_id: str,
        event: Event,
    ) -> list[EventEpisode]:
        return self.memory.retrieve_similar(user_id, event)

    def record_event_outcome(
        self,
        profile: UserProfile | dict[str, Any],
        event: Event | dict[str, Any],
        feedback: EventFeedback | dict[str, Any],
        recommendation: Recommendation | dict[str, Any] | None = None,
        *,
        episode_id: str | None = None,
        observed_at: str | None = None,
        storage_mode: str | None = None,
    ) -> EventEpisode:
        if not isinstance(profile, UserProfile):
            profile = UserProfile.from_dict(profile)
        if not isinstance(event, Event):
            event = Event.from_dict(event)
        if not isinstance(feedback, EventFeedback):
            feedback = EventFeedback.from_dict(feedback)
        if recommendation is not None and not isinstance(
            recommendation,
            Recommendation,
        ):
            recommendation = Recommendation.from_dict(recommendation)
        if feedback.user_id != profile.user_id:
            raise ValueError("feedback.user_id must match profile.user_id")
        if feedback.event_id != event.event_id:
            raise ValueError("feedback.event_id must match event.event_id")
        recommendation = recommendation or score_event(
            event,
            profile,
            run_id="run_feedback_source_v1",
        )
        if recommendation.event_id != event.event_id:
            raise ValueError("recommendation.event_id must match event.event_id")

        actual_scores = feedback_outcome_scores(feedback)
        episode = EventEpisode(
            schema_version=SCHEMA_VERSION,
            episode_id=episode_id or f"episode_{uuid4().hex[:10]}",
            user_id=profile.user_id,
            event_id=event.event_id,
            recommendation=recommendation,
            feedback=feedback,
            actual_scores=actual_scores,
            actual_event_success=actual_event_success(actual_scores),
            scoring_version=SCORING_VERSION,
            observed_at=observed_at or datetime.now(timezone.utc).isoformat(),
            storage_mode=storage_mode or self.memory.storage_mode,
        )
        self.memory.record(episode, event)
        return episode

    def score_with_memory(
        self,
        event: Event,
        profile: UserProfile,
        *,
        run_id: str,
    ) -> Recommendation:
        baseline = score_event(event, profile, run_id=run_id)
        similar = self.retrieve_similar_experiences(profile.user_id, event)
        if not similar:
            return baseline

        averages = {
            dimension: fmean(
                episode.actual_scores[dimension] for episode in similar
            )
            for dimension in (
                "networking",
                "knowledge",
                "opportunity",
                "personal_fit",
            )
        }
        learned_components = {
            dimension: clamp(
                0.65 * baseline.scores[dimension]
                + 0.35 * averages[dimension]
            )
            for dimension in averages
        }
        learned_overall = overall_score(
            learned_components,
            baseline.scores["friction"],
            profile,
        )
        overall_delta = learned_overall - baseline.scores["overall"]
        evidence_summary = (
            f"{len(similar)} similar recorded event experience(s) averaged "
            f"{round(fmean(item.actual_event_success for item in similar))}/100 "
            "actual success."
        )
        retrieval_evidence = self.memory.last_retrieval_evidence
        if retrieval_evidence and any(
            item.provider == "actian_vectorai"
            for item in retrieval_evidence
        ):
            top_relevance = max(item.relevance for item in retrieval_evidence)
            evidence_summary += (
                " Actian semantic memory selected the same-user evidence "
                f"(top relevance {top_relevance:.3f})."
            )
        elif retrieval_evidence and any(
            item.provider == "local_json"
            for item in retrieval_evidence
        ):
            top_relevance = max(item.relevance for item in retrieval_evidence)
            evidence_summary += (
                " Local deterministic structured-event similarity selected "
                f"the same-user evidence (top relevance {top_relevance:.3f})."
            )
        adjustments = [
            {
                "component": dimension,
                "delta": learned_components[dimension]
                - baseline.scores[dimension],
                "evidence_summary": evidence_summary,
            }
            for dimension in (
                "networking",
                "knowledge",
                "opportunity",
                "personal_fit",
            )
            if learned_components[dimension] != baseline.scores[dimension]
        ]

        return replace(
            baseline,
            scores={
                **learned_components,
                "friction": baseline.scores["friction"],
                "overall": learned_overall,
            },
            reasons=[
                f"Recorded feedback changed the overall score by {overall_delta:+d} "
                f"({baseline.scores['overall']} to {learned_overall}).",
                evidence_summary,
                *baseline.reasons,
            ],
            influencing_episode_ids=[item.episode_id for item in similar],
            confidence=min(0.95, baseline.confidence + 0.08 * len(similar)),
            adjustments=adjustments,
        )

    def rank_events_with_memory(
        self,
        profile: UserProfile,
        events: list[Event],
        limit: int | None = 3,
        *,
        run_id: str = "run_local_after_v1",
    ) -> list[Recommendation]:
        ranked = sorted(
            (
                self.score_with_memory(event, profile, run_id=run_id)
                for event in events
            ),
            key=lambda item: (-item.scores["overall"], item.event_id),
        )
        ranked = [
            replace(item, rank=index)
            for index, item in enumerate(ranked, start=1)
        ]
        return ranked if limit is None else ranked[:limit]

    def comparison(
        self,
        profile: UserProfile,
        events: list[Event],
        limit: int | None = 3,
    ) -> dict[str, list[Recommendation]]:
        return {
            "before": rank_events(
                events,
                profile,
                limit=limit,
                run_id="run_local_before_v1",
            ),
            "after": self.rank_events_with_memory(
                profile,
                events,
                limit=limit,
                run_id="run_local_after_v1",
            ),
        }


def default_engine() -> IntelligenceEngine:
    configured_path = os.getenv("EVENT_COPILOT_EPISODES_PATH")
    fallback_path = (
        Path(configured_path)
        if configured_path
        else Path(tempfile.gettempdir())
        / f"event-copilot-episodes-{os.getpid()}.json"
    )
    return IntelligenceEngine(create_episode_memory(fallback_path))


def retrieve_similar_experiences(
    user_id: str,
    event: Event,
) -> list[EventEpisode]:
    return default_engine().retrieve_similar_experiences(user_id, event)


def record_event_outcome(
    profile: UserProfile,
    event: Event,
    feedback: EventFeedback,
    recommendation: Recommendation | None = None,
) -> EventEpisode:
    return default_engine().record_event_outcome(
        profile,
        event,
        feedback,
        recommendation,
    )


def rank_events_with_memory(
    user_profile: UserProfile,
    events: list[Event],
) -> list[Recommendation]:
    return default_engine().rank_events_with_memory(user_profile, events)
