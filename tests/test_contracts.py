import json
import unittest
from pathlib import Path

from shared.contracts import Event, EventFeedback, Recommendation, UserProfile


ROOT = Path(__file__).resolve().parents[1]


class ContractTests(unittest.TestCase):
    def test_shared_fixtures_match_contracts(self) -> None:
        with (ROOT / "shared" / "sample_events.json").open(encoding="utf-8") as handle:
            events = [Event.from_dict(item) for item in json.load(handle)]
        with (ROOT / "shared" / "sample_profile.json").open(encoding="utf-8") as handle:
            profile = UserProfile.from_dict(json.load(handle))
        with (ROOT / "shared" / "sample_feedback.json").open(encoding="utf-8") as handle:
            feedback = EventFeedback.from_dict(json.load(handle))
        with (ROOT / "shared" / "mock_recommendations.json").open(encoding="utf-8") as handle:
            recommendations = [Recommendation.from_dict(item) for item in json.load(handle)]

        self.assertEqual(len(events), 9)
        self.assertEqual(profile.user_id, "demo_gergana")
        self.assertEqual(feedback.event_id, "evt_001")
        self.assertEqual(len(recommendations), 3)

    def test_invalid_score_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            Recommendation(
                event_id="evt_bad",
                scores={
                    "networking": 101,
                    "knowledge": 50,
                    "opportunity": 50,
                    "personal_fit": 50,
                    "friction": 0,
                    "overall": 50,
                },
                reasons=[],
                similar_past_events=[],
                confidence=0.5,
                citations=[],
            )


if __name__ == "__main__":
    unittest.main()
