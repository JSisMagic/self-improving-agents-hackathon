import asyncio
import unittest

from product.agents import run_agent_handoff
from product.band_orchestration import (
    BandAgentIdentity,
    BandConfiguration,
    BandEnvelope,
    BandOrchestrator,
    BandRequestClient,
    BandRoleHandler,
    BandRunBroker,
    parse_band_message,
    render_band_message,
)
from product.schema_validation import validate_schema
from product.ui import load_canonical_demo


class _FakeBandTools:
    def __init__(self, label="agent") -> None:
        self.label = label
        self.messages = []
        self.events = []

    async def send_message(self, content, mentions=None):
        message = {
            "id": f"band_message_{self.label}_{len(self.messages) + 1}",
            "content": content,
            "mentions": list(mentions or []),
        }
        self.messages.append(message)
        return message

    async def send_event(self, content, message_type, metadata=None):
        event = {
            "id": f"band_event_{self.label}_{len(self.events) + 1}",
            "content": content,
            "message_type": message_type,
            "metadata": dict(metadata or {}),
        }
        self.events.append(event)
        return event


def _configuration(*, enabled=True, with_credentials=True):
    agents = {}
    for role in ("coordinator", "scout", "analyst", "coach"):
        agents[role] = BandAgentIdentity(
            role=role,
            agent_id=f"{role}-agent-id" if with_credentials else "",
            api_key=f"{role}-api-key" if with_credentials else "",
        )
    return BandConfiguration(
        enabled=enabled,
        rest_url="https://app.band.ai",
        ws_url="wss://app.band.ai/api/v1/socket/websocket",
        timeout_seconds=1.0,
        startup_timeout_seconds=1.0,
        agents=agents,
    )


class BandOrchestrationTests(unittest.TestCase):
    def test_agent_api_requests_match_band_contract(self) -> None:
        calls = []

        def request_json(method, path, payload, timeout_seconds):
            calls.append((method, path, payload, timeout_seconds))
            if path == "/chats":
                return {"data": {"id": "band-room-1"}}
            if path.endswith("/participants") and method == "GET":
                return {
                    "data": [
                        {
                            "id": "scout-agent-id",
                            "handle": "event.scout",
                            "name": "Event Scout",
                        }
                    ]
                }
            if path.endswith("/messages"):
                return {"data": {"id": "band-message-1", "success": True}}
            return {"data": {}}

        client = BandRequestClient(
            _configuration(),
            request_json=request_json,
        )

        self.assertEqual(client.create_room(), "band-room-1")
        client.add_participant("band-room-1", "scout-agent-id")
        self.assertEqual(
            client.send_to_scout("band-room-1", "@Scout validate candidates"),
            "band-message-1",
        )

        self.assertEqual(
            calls[0][:3],
            ("POST", "/chats", {"chat": {}}),
        )
        self.assertEqual(
            calls[1][:3],
            (
                "POST",
                "/chats/band-room-1/participants",
                {"participant": {"participant_id": "scout-agent-id"}},
            ),
        )
        self.assertEqual(
            calls[3][2]["message"]["mentions"],
            [
                {
                    "id": "scout-agent-id",
                    "handle": "event.scout",
                    "name": "Event Scout",
                }
            ],
        )

    def test_wire_envelope_is_readable_and_round_trips(self) -> None:
        envelope = BandEnvelope(
            stage="scout_request",
            run_id="run_band_test",
            from_role="coordinator",
            to_role="scout",
            summary="Validate three candidates.",
            payload={"events": [{"event_id": "evt_1"}]},
        )

        rendered = render_band_message(envelope, "Scout")
        parsed = parse_band_message(rendered)

        self.assertTrue(rendered.startswith("@Scout Validate three candidates."))
        self.assertEqual(parsed, envelope)

    def test_four_identities_complete_a_targeted_band_handoff(self) -> None:
        profile, events, _ = load_canonical_demo()
        profile_payload = profile.to_dict()
        event_payloads = [event.to_dict() for event in events]
        run_id = "run_band_contract"
        config = _configuration()
        broker = BandRunBroker()
        broker.register(run_id)

        async def exercise():
            scout_tools = _FakeBandTools("scout")
            analyst_tools = _FakeBandTools("analyst")
            coach_tools = _FakeBandTools("coach")
            coordinator_tools = _FakeBandTools("coordinator")

            initial = render_band_message(
                BandEnvelope(
                    stage="scout_request",
                    run_id=run_id,
                    from_role="coordinator",
                    to_role="scout",
                    summary="Validate candidates.",
                    payload={
                        "profile": profile_payload,
                        "events": event_payloads,
                    },
                ),
                "Scout",
            )
            await BandRoleHandler("scout", config, broker).handle(
                content=initial,
                room_id="band-room-1",
                message_id="band_message_initial",
                tools=scout_tools,
            )
            analyst_message = scout_tools.messages[-1]
            self.assertEqual(
                analyst_message["mentions"],
                ["analyst-agent-id"],
            )
            self.assertEqual(
                parse_band_message(analyst_message["content"]).stage,
                "analyst_request",
            )

            await BandRoleHandler("analyst", config, broker).handle(
                content=analyst_message["content"],
                room_id="band-room-1",
                message_id=analyst_message["id"],
                tools=analyst_tools,
            )
            coach_message = analyst_tools.messages[-1]
            self.assertEqual(coach_message["mentions"], ["coach-agent-id"])

            await BandRoleHandler("coach", config, broker).handle(
                content=coach_message["content"],
                room_id="band-room-1",
                message_id=coach_message["id"],
                tools=coach_tools,
            )
            completion_message = coach_tools.messages[-1]
            self.assertEqual(
                completion_message["mentions"],
                ["coordinator-agent-id"],
            )

            await BandRoleHandler("coordinator", config, broker).handle(
                content=completion_message["content"],
                room_id="band-room-1",
                message_id=completion_message["id"],
                tools=coordinator_tools,
            )

        asyncio.run(exercise())
        result, transcript = broker.wait(run_id, 0.1)

        self.assertEqual(result["mode"], "connected")
        self.assertEqual(
            [item["event_id"] for item in result["recommendations"]],
            [
                "evt_mixer_001",
                "evt_workshop_001",
                "evt_live_swarmhack_20260724",
            ],
        )
        for recommendation in result["recommendations"]:
            validate_schema(recommendation, "recommendation")
        validate_schema(result["mission"], "mission")
        self.assertEqual(
            [(item["from"], item["to"]) for item in transcript],
            [
                ("Coordinator", "Scout"),
                ("Scout", "Analyst"),
                ("Analyst", "Coach"),
                ("Coach", "Coordinator"),
            ],
        )

    def test_disabled_band_uses_truthful_direct_call_fallback(self) -> None:
        profile, events, _ = load_canonical_demo()

        def fallback(profile_value, event_values, run_id):
            return run_agent_handoff(
                profile_value,
                event_values,
                run_id=run_id,
            )

        orchestrator = BandOrchestrator(
            fallback,
            configuration=_configuration(enabled=False),
        )
        result = orchestrator.coordinate(profile, events, "run_local_fallback")

        self.assertEqual(result["mode"], "demo_fallback")
        self.assertEqual(result["band"]["mode"], "disabled")
        self.assertIsNone(result["band"]["room_id"])
        self.assertEqual(result["band"]["transcript"], [])

    def test_incomplete_band_configuration_does_not_claim_connected(self) -> None:
        profile, events, _ = load_canonical_demo()

        def fallback(profile_value, event_values, run_id):
            return run_agent_handoff(
                profile_value,
                event_values,
                run_id=run_id,
            )

        orchestrator = BandOrchestrator(
            fallback,
            configuration=_configuration(
                enabled=True,
                with_credentials=False,
            ),
        )
        result = orchestrator.coordinate(profile, events, "run_missing_config")

        self.assertEqual(result["mode"], "demo_fallback")
        self.assertEqual(result["band"]["mode"], "disabled")
        self.assertIn(
            "BAND_SCOUT_API_KEY",
            result["band"]["missing_configuration"],
        )


if __name__ == "__main__":
    unittest.main()
