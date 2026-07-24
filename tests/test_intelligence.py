import json
import tempfile
import unittest
from pathlib import Path

from intelligence.actian_memory import ActianMemory
from intelligence.event_extractor import normalize_event
from intelligence.learning_loop import IntelligenceEngine
from intelligence.scorer import rank_events
from shared.contracts import Event, EventFeedback, UserProfile


ROOT = Path(__file__).resolve().parents[1]


class IntelligenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with (ROOT / "shared" / "sample_events.json").open(encoding="utf-8") as handle:
            cls.events = [Event.from_dict(item) for item in json.load(handle)]
        with (ROOT / "shared" / "sample_profile.json").open(encoding="utf-8") as handle:
            cls.profile = UserProfile.from_dict(json.load(handle))

    def test_baseline_and_memory_rankings_visibly_change(self) -> None:
        baseline = rank_events(self.events, self.profile)
        engine = IntelligenceEngine(ActianMemory(ROOT / "shared" / "actian_memories.json"))
        learned = engine.rank_events_with_memory(self.profile, self.events)

        self.assertEqual(baseline[0].event_id, "evt_001")
        self.assertEqual(learned[0].event_id, "evt_002")
        self.assertGreater(learned[0].scores["overall"], baseline[1].scores["overall"])
        mixer_after = next(item for item in engine.rank_events_with_memory(self.profile, self.events, None) if item.event_id == "evt_001")
        self.assertLess(mixer_after.scores["overall"], baseline[0].scores["overall"])

    def test_feedback_can_be_recorded_without_mutating_seed_data(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "memory.json"
            path.write_text("[]\n", encoding="utf-8")
            engine = IntelligenceEngine(ActianMemory(path))
            event = self.events[0]
            feedback = EventFeedback(
                event_id=event.event_id,
                meaningful_conversations=2,
                contacts_exchanged=1,
                followups_sent=1,
                meetings_booked=0,
                questions_answered=2,
                actionable_insights=1,
                opportunities_created=0,
                energy_after=6,
                overall_value=7,
            )
            engine.record_event_outcome(self.profile.user_id, event, feedback)
            self.assertEqual(len(engine.memory.all(self.profile.user_id)), 1)

    def test_raw_event_normalization(self) -> None:
        event = normalize_event(
            {
                "name": "Agent Meetup",
                "url": "https://example.com/meetup",
                "date": "2026-08-03T18:00:00-07:00",
                "tags": "AI agents, founders",
                "capacity": 60,
            }
        )
        self.assertTrue(event.event_id.startswith("evt_"))
        self.assertEqual(event.themes, ["AI agents", "founders"])
        self.assertEqual(event.estimated_crowd_size, 60)


if __name__ == "__main__":
    unittest.main()
