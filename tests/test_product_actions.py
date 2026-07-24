import unittest
from time import monotonic, sleep

from product.cited_publisher import publish_markdown, publish_mission
from product.payment_endpoint import request_playbook
from product.ui import EventCopilotUI


class _PublisherStub:
    provider = "cited.md"

    def publish_markdown(self, markdown: str, *, timeout_seconds: float):
        self.markdown = markdown
        return {
            "provider": self.provider,
            "status": "published",
            "remote_id": "publication_demo_001",
            "remote_url": "https://cited.example/publication_demo_001?token=redacted",
        }


class _PaymentStub:
    provider = "x402"
    network = "base-sepolia-testnet"

    def authorize_playbook(self, request, *, timeout_seconds: float):
        self.request = request
        return {
            "provider": self.provider,
            "status": "payment_required",
            "network": self.network,
            "request_id": "payment_request_demo_001",
            "payment_url": "https://pay.example/request/001?secret=redacted",
        }


class ProductActionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        ui = EventCopilotUI()
        ui.load_demo_profile()
        ui.run_initial_recommendation()
        ui.select_event("evt_mixer_001")
        ui.generate_event_mission(attempt_publish=False)
        cls.mission = ui.state.mission
        cls.event = ui.state.events[0]
        cls.markdown = ui.state.mission_markdown
        ui.close()

    def test_default_publication_is_only_a_local_preview(self) -> None:
        result = publish_markdown(self.markdown)

        self.assertEqual(result.mode, "demo_fallback")
        self.assertEqual(result.status, "preview")
        self.assertEqual(result.local_content, self.markdown)
        self.assertIsNone(result.remote_id)
        self.assertIsNone(result.remote_url)

    def test_connected_publication_requires_inspectable_evidence(self) -> None:
        adapter = _PublisherStub()
        result = publish_mission(self.mission, self.event, adapter=adapter)

        self.assertEqual(result.mode, "connected")
        self.assertEqual(result.status, "published")
        self.assertEqual(result.remote_id, "publication_demo_001")
        self.assertEqual(
            result.remote_url,
            "https://cited.example/publication_demo_001",
        )
        self.assertIn("## Sources", adapter.markdown)

    def test_payment_defaults_to_disabled_demo_without_transaction_claims(self) -> None:
        result = request_playbook(
            "evt_mixer_001",
            self.mission,
            payments_enabled=False,
        )

        self.assertEqual(result.mode, "disabled")
        self.assertEqual(result.status, "disabled")
        self.assertEqual(result.payment_mode, "demo")
        self.assertIsNotNone(result.playbook)
        self.assertIsNone(result.payment)

    def test_connected_x402_stub_is_testnet_and_inspectable(self) -> None:
        adapter = _PaymentStub()
        result = request_playbook(
            "evt_mixer_001",
            self.mission,
            adapter=adapter,
            payments_enabled=True,
        )

        self.assertEqual(result.mode, "connected")
        self.assertEqual(result.status, "payment_required")
        self.assertEqual(result.payment_mode, "x402_testnet")
        self.assertEqual(result.payment["network"], "base-sepolia-testnet")
        self.assertEqual(result.payment["request_id"], "payment_request_demo_001")
        self.assertEqual(
            result.payment["payment_url"],
            "https://pay.example/request/001",
        )
        self.assertIsNone(result.playbook)

    def test_adapter_errors_are_sanitized(self) -> None:
        def failing_adapter(markdown: str):
            raise RuntimeError("secret-token=should-never-appear")

        result = publish_markdown(self.markdown, adapter=failing_adapter)

        self.assertEqual(result.mode, "error")
        self.assertEqual(result.error["code"], "adapter_error")
        self.assertNotIn("secret-token", str(result.to_dict()))

    def test_publication_timeout_does_not_block_process_cleanup(self) -> None:
        def slow_adapter(markdown: str):
            sleep(0.25)
            return {"status": "published", "remote_id": "too_late"}

        started = monotonic()
        result = publish_markdown(
            self.markdown,
            adapter=slow_adapter,
            timeout_seconds=0.01,
        )

        self.assertLess(monotonic() - started, 0.1)
        self.assertEqual(result.mode, "error")
        self.assertEqual(result.error["code"], "adapter_timeout")

    def test_payment_timeout_does_not_block_process_cleanup(self) -> None:
        def slow_adapter(request):
            sleep(0.25)
            return {
                "status": "payment_required",
                "network": "base-sepolia-testnet",
                "request_id": "too_late",
            }

        started = monotonic()
        result = request_playbook(
            "evt_mixer_001",
            self.mission,
            adapter=slow_adapter,
            payments_enabled=True,
            timeout_seconds=0.01,
        )

        self.assertLess(monotonic() - started, 0.1)
        self.assertEqual(result.mode, "error")
        self.assertEqual(result.error["code"], "adapter_timeout")


if __name__ == "__main__":
    unittest.main()
