import unittest

from product.schema_validation import SchemaValidationError, validate_schema
from product.ui import (
    BrowserDemoApplication,
    CANONICAL_PROSPECTIVE_EVENT,
    EventCopilotUI,
    UIFlowError,
    load_canonical_demo,
)


class ProductFlowTests(unittest.TestCase):
    def test_canonical_inputs_validate_against_frozen_schemas(self) -> None:
        profile, events, feedback = load_canonical_demo()

        validate_schema(profile.to_dict(), "profile")
        self.assertEqual(len(events), 3)
        for event in events:
            validate_schema(event.to_dict(), "event")
        validate_schema(feedback.to_dict(), "feedback")

    def test_schema_validator_rejects_date_only_values(self) -> None:
        _, events, _ = load_canonical_demo()
        invalid_event = events[0].to_dict()
        invalid_event["start_time"] = "2026-07-25"

        with self.assertRaises(SchemaValidationError):
            validate_schema(invalid_event, "event")

    def test_full_local_journey_is_truthful_and_learns(self) -> None:
        ui = EventCopilotUI()
        self.addCleanup(ui.close)
        state = ui.run_all()

        self.assertEqual(
            [item.event_id for item in state.events],
            [
                "evt_mixer_001",
                "evt_workshop_001",
                "evt_live_swarmhack_20260724",
            ],
        )
        self.assertEqual(
            [item["event_id"] for item in state.initial_recommendations],
            [
                "evt_mixer_001",
                "evt_workshop_001",
                "evt_live_swarmhack_20260724",
            ],
        )
        for recommendation in state.initial_recommendations:
            validate_schema(recommendation, "recommendation")

        self.assertEqual(state.selected_event_id, "evt_mixer_001")
        validate_schema(state.mission, "mission")
        self.assertIn("## Sources", state.mission_markdown)
        self.assertIn("https://example.com/events/ai-founders-mixer", state.mission_markdown)

        self.assertEqual(state.publication.mode, "demo_fallback")
        self.assertEqual(state.publication.status, "preview")
        self.assertIsNone(state.publication.remote_url)
        self.assertEqual(state.playbook.mode, "disabled")
        self.assertEqual(state.playbook.status, "disabled")
        self.assertEqual(state.playbook.payment_mode, "demo")
        self.assertIsNone(state.playbook.payment)

        validate_schema(state.episode.to_dict(), "episode")
        validate_schema(state.prospective_event, "event")
        next_event_ids = {
            item.event_id if hasattr(item, "event_id") else item["event_id"]
            for item in state.next_events
        }
        self.assertNotIn("evt_mixer_001", next_event_ids)
        self.assertEqual(
            next_event_ids,
            {
                "evt_workshop_001",
                "evt_live_swarmhack_20260724",
                "evt_live_step_sf_20260827",
            },
        )
        improved = [item.to_dict() for item in state.improved_recommendations]
        for recommendation in improved:
            validate_schema(recommendation, "recommendation")
        self.assertEqual(improved[0]["event_id"], "evt_workshop_001")
        self.assertEqual(improved[2]["event_id"], "evt_live_step_sf_20260827")
        prospect = improved[2]
        self.assertLess(
            prospect["scores"]["overall"],
            72,
        )
        self.assertIn(
            state.episode.episode_id,
            prospect["influencing_episode_ids"],
        )
        self.assertIn("recorded feedback", prospect["reasons"][0].lower())
        self.assertEqual(state.next_event_modes[prospect["event_id"]], "live")
        self.assertEqual(
            prospect["citations"][0]["url"],
            "https://luma.com/StepSF26",
        )

        rendered = ui.render()
        self.assertIn("Scout →", rendered)
        self.assertIn("Analyst →", rendered)
        self.assertIn("Coach → Risk:", rendered)
        self.assertIn("NEXT-EVENT RECOMMENDATIONS", rendered)
        self.assertIn("Step SF 2026", rendered)
        self.assertIn(
            "Delta: NEW prospective event; no prior rank or score.",
            rendered,
        )
        self.assertIn(state.episode.episode_id, rendered)

    def test_after_state_requires_a_successful_episode_write(self) -> None:
        ui = EventCopilotUI()
        self.addCleanup(ui.close)
        ui.load_demo_profile()
        ui.run_initial_recommendation()

        with self.assertRaisesRegex(UIFlowError, "No successful episode write"):
            ui.show_improved_recommendations()

    def test_two_fresh_rehearsals_do_not_share_episode_state(self) -> None:
        first = EventCopilotUI()
        self.addCleanup(first.close)
        first_state = first.run_all()
        second = EventCopilotUI()
        self.addCleanup(second.close)
        second_state = second.run_all()

        self.assertNotEqual(first_state.episode.episode_id, second_state.episode.episode_id)
        self.assertEqual(
            [item.scores["overall"] for item in first_state.improved_recommendations],
            [item.scores["overall"] for item in second_state.improved_recommendations],
        )

    def test_browser_forms_accept_contract_shaped_setup_and_feedback(self) -> None:
        profile, events, feedback = load_canonical_demo()
        app = BrowserDemoApplication(EventCopilotUI())
        self.addCleanup(app.close)

        configured = app.configure(
            profile.to_dict(),
            [event.to_dict() for event in events],
        )
        self.assertEqual(configured["stage"], 1)
        self.assertEqual(configured["profile"]["user_id"], profile.user_id)
        self.assertEqual(len(configured["events"]), 3)

        app.run_control(2)
        app.select_event("evt_mixer_001")
        app.run_control(3)
        app.run_control(4)
        recorded = app.record_feedback(feedback.to_dict())
        self.assertEqual(recorded["stage"], 5)
        self.assertEqual(
            recorded["episode"]["feedback"]["free_text_feedback"],
            feedback.free_text_feedback,
        )

        improved = app.evaluate_prospect(CANONICAL_PROSPECTIVE_EVENT)
        self.assertEqual(improved["stage"], 6)
        self.assertEqual(
            improved["improved_recommendations"][0]["event_id"],
            "evt_workshop_001",
        )
        self.assertEqual(
            improved["prospective_event"]["event_id"],
            "evt_live_step_sf_20260827",
        )
        self.assertNotIn(
            "evt_mixer_001",
            {event["event_id"] for event in improved["next_events"]},
        )
        prospect = next(
            item
            for item in improved["improved_recommendations"]
            if item["event_id"] == "evt_live_step_sf_20260827"
        )
        self.assertIn(
            improved["episode"]["episode_id"],
            prospect["influencing_episode_ids"],
        )

    def test_browser_form_setup_rejects_invalid_contract_input(self) -> None:
        profile, events, _ = load_canonical_demo()
        invalid_profile = profile.to_dict()
        invalid_profile["role"] = ""
        app = BrowserDemoApplication(EventCopilotUI())
        self.addCleanup(app.close)

        with self.assertRaisesRegex(UIFlowError, "Profile failed profile validation"):
            app.configure(
                invalid_profile,
                [event.to_dict() for event in events],
            )


if __name__ == "__main__":
    unittest.main()
