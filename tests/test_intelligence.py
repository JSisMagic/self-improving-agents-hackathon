import json
import tempfile
import unittest
from pathlib import Path

from intelligence.actian_memory import ActianMemory
from intelligence.event_extractor import normalize_event
from intelligence.learning_loop import (
    IntelligenceEngine,
    actual_event_success,
    feedback_outcome_scores,
)
from intelligence.scorer import rank_events
from shared.contracts import Event, EventFeedback, UserProfile


ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path):
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


class IntelligenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.events = [
            Event.from_dict(item)
            for item in load_json(ROOT / "shared" / "sample_events.json")
        ]
        cls.profile = UserProfile.from_dict(
            load_json(ROOT / "shared" / "sample_profile.json")
        )
        cls.feedback = EventFeedback.from_dict(
            load_json(ROOT / "shared" / "sample_feedback.json")
        )

    def test_deliberate_feedback_writes_episode_then_reverses_ranking(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            engine = IntelligenceEngine(
                ActianMemory(Path(directory) / "episodes.json")
            )
            before = rank_events(
                self.events,
                self.profile,
                limit=None,
                run_id="run_test_before_v1",
            )
            mixer = next(
                item
                for item in self.events
                if item.event_id == self.feedback.event_id
            )
            mixer_before = next(
                item
                for item in before
                if item.event_id == self.feedback.event_id
            )
            episode = engine.record_event_outcome(
                self.profile,
                mixer,
                self.feedback,
                mixer_before,
                episode_id="episode_test_mixer_001",
                observed_at="2026-07-26T12:00:00-07:00",
            )
            after = engine.rank_events_with_memory(
                self.profile,
                self.events,
                limit=None,
                run_id="run_test_after_v1",
            )

            workshop_after = next(
                item
                for item in after
                if item.event_id == "evt_workshop_001"
            )
            mixer_after = next(
                item
                for item in after
                if item.event_id == self.feedback.event_id
            )
            self.assertEqual(before[0].event_id, "evt_mixer_001")
            self.assertEqual(workshop_after.rank, 1)
            self.assertEqual(mixer_after.rank, 3)
            self.assertLess(
                mixer_after.scores["overall"],
                mixer_before.scores["overall"],
            )
            self.assertEqual(
                mixer_after.influencing_episode_ids,
                [episode.episode_id],
            )
            self.assertTrue(mixer_after.adjustments)
            self.assertEqual(len(engine.memory.all(self.profile.user_id)), 1)
            self.assertEqual(
                engine.memory.all(self.profile.user_id)[0].to_dict(),
                episode.to_dict(),
            )

    def test_feedback_uses_accepted_version_one_formula(self) -> None:
        scores = feedback_outcome_scores(self.feedback)
        self.assertEqual(
            scores,
            {
                "networking": 100,
                "knowledge": 35,
                "opportunity": 0,
                "personal_fit": 45,
            },
        )
        self.assertEqual(actual_event_success(scores), 45)

    def test_baseline_scores_are_deterministic_and_use_friction_penalty(
        self,
    ) -> None:
        first = rank_events(
            self.events,
            self.profile,
            limit=None,
            run_id="run_determinism_v1",
        )
        second = rank_events(
            self.events,
            self.profile,
            limit=None,
            run_id="run_determinism_v1",
        )
        self.assertEqual(
            [item.to_dict() for item in first],
            [item.to_dict() for item in second],
        )
        self.assertEqual(first[0].scores["overall"], 81)

    def test_raw_event_normalization(self) -> None:
        event = normalize_event(
            {
                "name": "Agent Meetup",
                "description": "Builders compare agent-memory patterns.",
                "url": "https://example.com/meetup",
                "platform": "Example Events",
                "date": "2026-08-03T18:00:00-07:00",
                "location": "San Francisco",
                "tags": "AI agents, founders",
                "capacity": 60,
            }
        )
        self.assertTrue(event.event_id.startswith("evt_"))
        self.assertEqual(event.schema_version, "1.0")
        self.assertEqual(event.data_mode, "fixture")
        self.assertEqual(event.themes, ["AI agents", "founders"])
        self.assertEqual(event.estimated_crowd_size, 60)


if __name__ == "__main__":
    unittest.main()
