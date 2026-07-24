"""Small Pioneer adapter with a deterministic cache-first demo fallback."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen


class PioneerUnavailable(RuntimeError):
    """Raised when live Pioneer extraction cannot be used."""


class PioneerClient:
    def __init__(
        self,
        cache_path: str | Path,
        endpoint: str | None = None,
        api_key: str | None = None,
        timeout_seconds: float = 4.0,
    ) -> None:
        self.cache_path = Path(cache_path)
        self.endpoint = endpoint or os.getenv("PIONEER_API_URL")
        self.api_key = api_key or os.getenv("PIONEER_API_KEY")
        self.timeout_seconds = timeout_seconds

    @property
    def status(self) -> str:
        return "connected" if self.endpoint and self.api_key else "demo fallback"

    def extract_live(self, raw_event: dict[str, Any]) -> dict[str, Any]:
        if not self.endpoint or not self.api_key:
            raise PioneerUnavailable("Pioneer credentials are not configured")

        request = Request(
            self.endpoint,
            data=json.dumps({"event": raw_event}).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.load(response)
        except Exception as exc:  # Network/service errors are expected during the demo.
            raise PioneerUnavailable(str(exc)) from exc

        return payload.get("event", payload)

    def cached_extraction(self, event_id: str) -> dict[str, Any]:
        try:
            with self.cache_path.open(encoding="utf-8") as handle:
                cached = json.load(handle)
        except (FileNotFoundError, json.JSONDecodeError) as exc:
            raise PioneerUnavailable(f"Pioneer cache unavailable: {exc}") from exc

        if isinstance(cached, list):
            cached = {item["event_id"]: item for item in cached}
        try:
            return cached[event_id]
        except KeyError as exc:
            raise PioneerUnavailable(f"No cached extraction for {event_id}") from exc

    def extract(self, raw_event: dict[str, Any]) -> tuple[dict[str, Any], str]:
        try:
            return self.extract_live(raw_event), "connected"
        except PioneerUnavailable:
            event_id = str(raw_event.get("event_id", ""))
            return self.cached_extraction(event_id), "demo fallback"
