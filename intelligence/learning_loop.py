"""Fast feedback loop: retrieve outcomes, rerank, and record new evidence."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from statistics import fmean
from uuid import uuid4

from shared.contracts import Event, EventEpisode, EventFeedback, Recommendation, UserProfile

from .actian_memory import ActianMemory
from .scorer import rank_events, score_event


def feedback_outcome_scores(feedback: EventFeedback) -> dict[str, int]:
    """Turn measured real-world feedback into the four shared success dimensions."""

    networking = min(
        100,
        feedback.meaningful_conversations * 7
        + feedback.contacts_exchanged * 4
        + feedback.followups_sent * 7
        + feedback.meetings_booked * 20,
    )
    knowledge = min(100, feedback.questions_answered * 12 + feedback.actionable_insights * 17)
    opportunity = min(
        100,
        feedback.opportunities_created * 45
        + feedback.meetings_booked * 18
        + feedback.followups_sent * 4,
    )
    personal_fit = round((feedback.energy_after + feedback.overall_value) * 5)
    overall = round(0.30 * networking + 0.30 * knowledge + 0.30 * opportunity + 0.10 * personal_fit)
    return {
        "networking": networking,
        "knowledge": knowledge,
        "opportunity": opportunity,
        "personal_fit": personal_fit,
        "overall": overall,
    }


class IntelligenceEngine:
    def __init__(self, memory: ActianMemory) -> None:
        self.memory = memory

    def retrieve_similar_experiences(self, user_id: str, event: Event) -> list[EventEpisode]:
        return self.memory.retrieve_similar(user_id, event)

    def record_event_outcome(
        self,
        user_id: str,
        event: Event,
        feedback: EventFeedback,
    ) -> EventEpisode:
        if feedback.event_id != event.event_id:
            raise ValueError("feedback.event_id must match event.event_id")
        episode = EventEpisode(
            episode_id=f"episode_{uuid4().hex[:10]}",
            user_id=user_id,
            event=event,
            feedback=feedback,
            recorded_at=datetime.now(timezone.utc).isoformat(),
        )
        self.memory.record(episode)
        return episode

    def score_with_memory(self, event: Event, profile: UserProfile) -> Recommendation:
        baseline = score_event(event, profile)
        similar = self.retrieve_similar_experiences(profile.user_id, event)
        if not similar:
            return baseline

        outcomes = [feedback_outcome_scores(episode.feedback) for episode in similar]
        averages = {
            dimension: fmean(item[dimension] for item in outcomes)
            for dimension in ("networking", "knowledge", "opportunity", "personal_fit", "overall")
        }
        learned_components = {
            dimension: round(0.65 * baseline.scores[dimension] + 0.35 * averages[dimension])
            for dimension in ("networking", "knowledge", "opportunity", "personal_fit")
        }

        # Seventy is the neutral evidence point. Outcomes above it increase the
        # prediction; outcomes below it decrease it. This makes the change easy
        # to explain on stage while retaining half of the baseline prediction.
        learned_overall = round(baseline.scores["overall"] + 0.5 * (averages["overall"] - 70))
        learned_overall = max(0, min(100, learned_overall))
        confidence = min(0.95, 0.60 + 0.08 * len(similar))
        direction = "increased" if learned_overall > baseline.scores["overall"] else "decreased"

        return replace(
            baseline,
            scores={
                **learned_components,
                "friction": baseline.scores["friction"],
                "overall": learned_overall,
            },
            reasons=[
                f"Memory {direction} the score from {baseline.scores['overall']} to {learned_overall}.",
                f"{len(similar)} similar past event(s) averaged {round(averages['overall'])}/100 measured success.",
                *baseline.reasons,
            ],
            similar_past_events=[episode.episode_id for episode in similar],
            confidence=confidence,
        )

    def rank_events_with_memory(
        self,
        profile: UserProfile,
        events: list[Event],
        limit: int | None = 3,
    ) -> list[Recommendation]:
        ranked = sorted(
            (self.score_with_memory(event, profile) for event in events),
            key=lambda item: item.scores["overall"],
            reverse=True,
        )
        return ranked if limit is None else ranked[:limit]

    def comparison(
        self,
        profile: UserProfile,
        events: list[Event],
        limit: int | None = 3,
    ) -> dict[str, list[Recommendation]]:
        return {
            "before": rank_events(events, profile, limit=limit),
            "after": self.rank_events_with_memory(profile, events, limit=limit),
        }


def default_engine() -> IntelligenceEngine:
    root = Path(__file__).resolve().parents[1]
    return IntelligenceEngine(ActianMemory(root / "shared" / "actian_memories.json"))


def retrieve_similar_experiences(user_id: str, event: Event) -> list[EventEpisode]:
    return default_engine().retrieve_similar_experiences(user_id, event)


def record_event_outcome(user_id: str, event: Event, feedback: EventFeedback) -> EventEpisode:
    return default_engine().record_event_outcome(user_id, event, feedback)


def rank_events_with_memory(user_profile: UserProfile, events: list[Event]) -> list[Recommendation]:
    return default_engine().rank_events_with_memory(user_profile, events)
