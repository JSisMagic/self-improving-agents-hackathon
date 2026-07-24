import json
import unittest
from pathlib import Path

from product.schema_validation import validate_schema
from shared.contracts import (
    Event,
    EventEpisode,
    EventFeedback,
    EventMission,
    Recommendation,
    UserProfile,
)


ROOT = Path(__file__).resolve().parents[1]
SHARED = ROOT / "shared"
SCHEMAS = ROOT / "specs" / "03-data" / "schemas"


def load_json(path: Path):
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def required_fields(schema_name: str) -> set[str]:
    return set(load_json(SCHEMAS / schema_name)["required"])


class ContractTests(unittest.TestCase):
    def assert_required_fields(
        self,
        payload: dict,
        schema_name: str,
    ) -> None:
        self.assertEqual(
            required_fields(schema_name) - set(payload),
            set(),
            f"{schema_name} required fields are missing",
        )

    def test_all_six_canonical_fixtures_match_contract_models(self) -> None:
        raw_events = load_json(SHARED / "sample_events.json")
        raw_profile = load_json(SHARED / "sample_profile.json")
        raw_recommendations = load_json(
            SHARED / "mock_recommendations.json"
        )
        raw_feedback = load_json(SHARED / "sample_feedback.json")
        raw_mission = load_json(SHARED / "sample_mission.json")
        raw_episode = load_json(SHARED / "sample_episode.json")

        events = [Event.from_dict(item) for item in raw_events]
        profile = UserProfile.from_dict(raw_profile)
        recommendations = [
            Recommendation.from_dict(item) for item in raw_recommendations
        ]
        feedback = EventFeedback.from_dict(raw_feedback)
        mission = EventMission.from_dict(raw_mission)
        episode = EventEpisode.from_dict(raw_episode)

        self.assertEqual(len(events), 3)
        self.assertEqual(
            [item.data_mode for item in events],
            ["fixture", "fixture", "live"],
        )
        self.assertEqual(profile.user_id, "demo_founder_001")
        self.assertEqual(len(recommendations), 3)
        self.assertEqual([item.rank for item in recommendations], [1, 2, 3])
        self.assertEqual(feedback.event_id, "evt_mixer_001")
        self.assertEqual(mission.event_id, feedback.event_id)
        self.assertEqual(episode.feedback.to_dict(), feedback.to_dict())
        self.assertEqual(episode.actual_event_success, 45)

        for payload in raw_events:
            validate_schema(payload, "event")
            self.assert_required_fields(payload, "event.schema.json")
        validate_schema(raw_profile, "profile")
        self.assert_required_fields(raw_profile, "profile.schema.json")
        for payload in raw_recommendations:
            validate_schema(payload, "recommendation")
            self.assert_required_fields(
                payload,
                "recommendation.schema.json",
            )
        validate_schema(raw_feedback, "feedback")
        self.assert_required_fields(raw_feedback, "feedback.schema.json")
        validate_schema(raw_mission, "mission")
        self.assert_required_fields(raw_mission, "mission.schema.json")
        validate_schema(raw_episode, "episode")
        self.assert_required_fields(raw_episode, "episode.schema.json")
        self.assert_required_fields(
            raw_episode["recommendation"],
            "recommendation.schema.json",
        )
        self.assert_required_fields(
            raw_episode["feedback"],
            "feedback.schema.json",
        )

    def test_derived_recommendation_fixtures_are_ordered_and_versioned(
        self,
    ) -> None:
        for name in (
            "mock_recommendations.json",
            "recommendations_before.json",
            "recommendations_after.json",
        ):
            payload = load_json(SHARED / name)
            recommendations = [
                Recommendation.from_dict(item) for item in payload
            ]
            for item in payload:
                validate_schema(item, "recommendation")
            self.assertEqual(len(recommendations), 3)
            self.assertEqual(
                [item.rank for item in recommendations],
                [1, 2, 3],
            )
            self.assertEqual(
                {item.scoring_version for item in recommendations},
                {"v1"},
            )

    def test_deferred_cache_is_contract_compatible_and_runtime_store_is_clean(
        self,
    ) -> None:
        events = load_json(SHARED / "sample_events.json")
        cached = load_json(SHARED / "pioneer_extractions.json")
        self.assertEqual(set(cached), {item["event_id"] for item in events})
        for payload in cached.values():
            validate_schema(payload, "event")
            Event.from_dict(payload)
        self.assertEqual(load_json(SHARED / "actian_memories.json"), [])

    def test_reader_ignores_unknown_optional_fields(self) -> None:
        payload = load_json(SHARED / "sample_events.json")[0]
        event = Event.from_dict(
            {**payload, "future_optional_field": {"value": 1}}
        )
        self.assertEqual(event.event_id, payload["event_id"])

    def test_invalid_score_is_rejected(self) -> None:
        payload = load_json(SHARED / "mock_recommendations.json")[0]
        payload["scores"]["networking"] = 101
        with self.assertRaises(ValueError):
            Recommendation.from_dict(payload)


if __name__ == "__main__":
    unittest.main()
