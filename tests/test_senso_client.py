import json
import unittest

from intelligence.senso_client import HttpResponse, SensoClient
from product.schema_validation import validate_schema


EVENT_URL = "https://events.example.org/agent-workshop"
EVENT_HTML = b"""<!doctype html>
<html>
  <head>
    <script type="application/ld+json">
      {
        "@context": "https://schema.org",
        "@type": "Event",
        "@id": "evt_live_agent_workshop",
        "name": "Live Agent Systems Workshop",
        "description": "<p>Build grounded agents with feedback loops.</p>",
        "startDate": "2026-08-03T18:00:00-07:00",
        "url": "https://canonical.example.net/ignored-for-grounding",
        "location": {
          "@type": "Place",
          "name": "Workshop Hall",
          "address": {
            "addressLocality": "San Francisco",
            "addressRegion": "CA"
          }
        },
        "keywords": "AI agents, feedback loops",
        "eventAttendanceMode": "OfflineEventAttendanceMode",
        "maximumAttendeeCapacity": 75,
        "offers": {"price": "12.50", "priceCurrency": "USD"}
      }
    </script>
  </head>
  <body><h1>Live Agent Systems Workshop</h1></body>
</html>"""


class RecordingHttp:
    def __init__(self, *, connected: bool = False) -> None:
        self.connected = connected
        self.calls = []

    def __call__(self, method, url, headers, data, timeout):
        self.calls.append((method, url, dict(headers), data, timeout))
        if method == "GET" and url == EVENT_URL:
            return HttpResponse(
                200,
                {"Content-Type": "text/html; charset=utf-8"},
                EVENT_HTML,
            )
        if method == "POST" and url.endswith("/org/kb/upload"):
            payload = json.loads(data)
            self.filename = payload["files"][0]["filename"]
            return HttpResponse(
                200,
                {"Content-Type": "application/json"},
                json.dumps(
                    {
                        "results": [
                            {
                                "content_id": "content_123",
                                "upload_url": "https://uploads.senso.example/signed",
                                "status": "upload_pending",
                            }
                        ]
                    }
                ).encode(),
            )
        if method == "PUT" and url == "https://uploads.senso.example/signed":
            return HttpResponse(200, {}, b"")
        if method == "GET" and "/org/kb/find?q=" in url:
            return HttpResponse(
                200,
                {"Content-Type": "application/json"},
                json.dumps(
                    {
                        "nodes": [
                            {
                                "content_id": "content_123",
                                "kb_node_id": "node_123",
                            }
                        ]
                    }
                ).encode(),
            )
        if method == "GET" and url.endswith("/org/kb/nodes/node_123/content"):
            return HttpResponse(
                200,
                {"Content-Type": "application/json"},
                b'{"processing_status":"complete"}',
            )
        raise AssertionError(f"unexpected HTTP call: {method} {url}")


class SensoClientTests(unittest.TestCase):
    def test_live_page_is_normalized_without_claiming_senso_connection(self):
        http = RecordingHttp()
        result = SensoClient(api_key=None, request=http).crawl_events([EVENT_URL])

        self.assertEqual(result.provider, "Senso")
        self.assertEqual(result.mode, "demo_fallback")
        self.assertEqual(len(result.events), 1)
        event = result.events[0]
        validate_schema(event.to_dict(), "event")
        self.assertEqual(event.data_mode, "live")
        self.assertEqual(event.event_id, "evt_live_agent_workshop")
        self.assertEqual(event.source_url, EVENT_URL)
        self.assertEqual(event.source_name, "events.example.org")
        self.assertEqual(event.themes, ["AI agents", "feedback loops"])
        self.assertEqual(event.estimated_crowd_size, 75)
        self.assertEqual(event.cost_usd, 12.5)
        self.assertEqual(result.senso_content_ids, [])
        self.assertEqual([call[0] for call in http.calls], ["GET"])

    def test_connected_mode_requires_successful_senso_compilation(self):
        http = RecordingHttp(connected=True)
        result = SensoClient(
            api_key="test-secret-key",
            request=http,
            sleeper=lambda _seconds: None,
        ).crawl_events([EVENT_URL])

        self.assertEqual(result.mode, "connected")
        self.assertEqual(result.senso_content_ids, ["content_123"])
        self.assertEqual(
            [call[0] for call in http.calls],
            ["GET", "POST", "PUT", "GET", "GET"],
        )
        upload_call = http.calls[1]
        self.assertEqual(upload_call[2]["X-API-Key"], "test-secret-key")
        self.assertEqual(upload_call[2]["User-Agent"], "senso-cli/0.11.1")
        snapshot_call = http.calls[2]
        self.assertEqual(snapshot_call[2]["User-Agent"], "senso-cli/0.11.1")
        self.assertIn(EVENT_URL.encode(), snapshot_call[3])

    def test_private_source_is_rejected_before_network_access(self):
        http = RecordingHttp()
        result = SensoClient(request=http).crawl_events(
            ["http://127.0.0.1/internal-event"]
        )

        self.assertEqual(result.mode, "error")
        self.assertEqual(result.events, [])
        self.assertIn("private or non-global", result.errors[0])
        self.assertEqual(http.calls, [])

    def test_missing_event_json_ld_returns_sanitized_error(self):
        def no_event_http(method, url, headers, data, timeout):
            return HttpResponse(
                200,
                {"Content-Type": "text/html"},
                b"<html><body>No structured event here.</body></html>",
            )

        result = SensoClient(
            api_key="do-not-leak",
            request=no_event_http,
        ).crawl_events([EVENT_URL])

        self.assertEqual(result.mode, "error")
        self.assertEqual(result.events, [])
        self.assertNotIn("do-not-leak", json.dumps(result.to_dict()))
        self.assertIn("no valid schema.org Event data", result.errors[0])


if __name__ == "__main__":
    unittest.main()
