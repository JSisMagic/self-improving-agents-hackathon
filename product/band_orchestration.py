"""Native Band coordination for Event Copilot's independent role agents.

Connected mode uses four Band remote-agent identities:

Coordinator -> Scout -> Analyst -> Coach -> Coordinator

Each role receives a targeted Band message over the SDK's WebSocket runtime,
calls the same deterministic domain function used by the local path, and sends
the next handoff through Band.  This module deliberately keeps Band's wire
envelope private to the integration; domain objects remain governed by the six
JSON Schemas in ``specs/03-data/schemas``.

The Band SDK is an optional dependency.  Importing this module never requires
it, and every configuration, startup, provider, or timeout failure returns the
existing direct-call path with a truthful ``demo_fallback`` status.
"""

from __future__ import annotations

import asyncio
import json
import os
import threading
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from time import monotonic
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


PROVIDER = "band"
PROTOCOL = "event-copilot.band/1"
PAYLOAD_MARKER = "\nEVENT_COPILOT_PAYLOAD="
DEFAULT_REST_URL = "https://app.band.ai"
DEFAULT_WS_URL = "wss://app.band.ai/api/v1/socket/websocket"
ROLE_ORDER = ("coordinator", "scout", "analyst", "coach")
EXPECTED_STAGE = {
    "coordinator": frozenset({"complete", "error"}),
    "scout": frozenset({"scout_request"}),
    "analyst": frozenset({"analyst_request"}),
    "coach": frozenset({"coach_request"}),
}

Record = Mapping[str, Any] | object
Fallback = Callable[[Record, Sequence[Record], str], Mapping[str, Any]]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _mapping(value: Record, label: str) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        converted = to_dict()
        if isinstance(converted, Mapping):
            return dict(converted)
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    raise TypeError(f"{label} must be a mapping or dataclass-like object")


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value.strip()


def _safe_summary(value: object) -> str:
    if not isinstance(value, str):
        return "Event Copilot agent handoff"
    return " ".join(value.split())[:240] or "Event Copilot agent handoff"


def _safe_error(code: str, message: str) -> dict[str, str]:
    return {
        "code": code,
        "message": _safe_summary(message),
    }


def _response_id(value: Any) -> str | None:
    if isinstance(value, Mapping):
        item = value.get("id")
    else:
        item = getattr(value, "id", None)
    return item if isinstance(item, str) and item.strip() else None


@dataclass(frozen=True, slots=True)
class BandAgentIdentity:
    """One independently authenticated remote-agent identity."""

    role: str
    agent_id: str
    api_key: str

    @classmethod
    def from_environment(cls, role: str) -> "BandAgentIdentity":
        prefix = f"BAND_{role.upper()}"
        return cls(
            role=role,
            agent_id=os.getenv(f"{prefix}_AGENT_ID", "").strip(),
            api_key=os.getenv(f"{prefix}_API_KEY", "").strip(),
        )


@dataclass(frozen=True, slots=True)
class BandConfiguration:
    """Sanitized runtime configuration; keys are never serialized."""

    enabled: bool
    rest_url: str
    ws_url: str
    timeout_seconds: float
    startup_timeout_seconds: float
    agents: dict[str, BandAgentIdentity]

    @classmethod
    def from_environment(cls) -> "BandConfiguration":
        enabled = os.getenv("BAND_ENABLED", "").strip().casefold() in {
            "1",
            "true",
            "yes",
            "on",
        }

        def positive_float(name: str, default: float) -> float:
            raw = os.getenv(name, "").strip()
            if not raw:
                return default
            try:
                value = float(raw)
            except ValueError:
                return default
            return value if value > 0 else default

        return cls(
            enabled=enabled,
            rest_url=os.getenv("BAND_REST_URL", DEFAULT_REST_URL).rstrip("/"),
            ws_url=os.getenv("BAND_WS_URL", DEFAULT_WS_URL),
            timeout_seconds=positive_float("BAND_TIMEOUT_SECONDS", 30.0),
            startup_timeout_seconds=positive_float(
                "BAND_STARTUP_TIMEOUT_SECONDS",
                20.0,
            ),
            agents={
                role: BandAgentIdentity.from_environment(role)
                for role in ROLE_ORDER
            },
        )

    def missing_fields(self) -> list[str]:
        missing: list[str] = []
        for role in ROLE_ORDER:
            identity = self.agents[role]
            prefix = f"BAND_{role.upper()}"
            if not identity.agent_id:
                missing.append(f"{prefix}_AGENT_ID")
            if not identity.api_key:
                missing.append(f"{prefix}_API_KEY")
        return missing

    def identity(self, role: str) -> BandAgentIdentity:
        try:
            return self.agents[role]
        except KeyError as exc:
            raise ValueError(f"Unknown Band role {role!r}") from exc


@dataclass(frozen=True, slots=True)
class BandEnvelope:
    """Integration-private handoff carried in one targeted Band message."""

    stage: str
    run_id: str
    from_role: str
    to_role: str
    summary: str
    payload: dict[str, Any]
    protocol: str = PROTOCOL

    def to_dict(self) -> dict[str, Any]:
        return {
            "protocol": self.protocol,
            "stage": self.stage,
            "run_id": self.run_id,
            "from": self.from_role,
            "to": self.to_role,
            "summary": _safe_summary(self.summary),
            "payload": self.payload,
        }


def render_band_message(envelope: BandEnvelope, target_label: str) -> str:
    """Render a readable Band message followed by its deterministic payload."""

    payload = json.dumps(
        envelope.to_dict(),
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return (
        f"@{target_label} {_safe_summary(envelope.summary)}"
        f"{PAYLOAD_MARKER}{payload}"
    )


def parse_band_message(content: str) -> BandEnvelope:
    """Parse and validate an Event Copilot message from a Band room."""

    if not isinstance(content, str) or PAYLOAD_MARKER not in content:
        raise ValueError("message does not contain an Event Copilot Band payload")
    raw = content.split(PAYLOAD_MARKER, 1)[1].strip()
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("Band handoff payload is not valid JSON") from exc
    if not isinstance(value, Mapping):
        raise ValueError("Band handoff payload must be an object")
    if value.get("protocol") != PROTOCOL:
        raise ValueError("unsupported Event Copilot Band protocol")

    payload = value.get("payload")
    if not isinstance(payload, Mapping):
        raise ValueError("Band handoff payload.payload must be an object")
    return BandEnvelope(
        stage=_text(value.get("stage"), "stage"),
        run_id=_text(value.get("run_id"), "run_id"),
        from_role=_text(value.get("from"), "from"),
        to_role=_text(value.get("to"), "to"),
        summary=_safe_summary(value.get("summary")),
        payload=dict(payload),
    )


@dataclass(slots=True)
class _PendingRun:
    event: threading.Event = field(default_factory=threading.Event)
    result: dict[str, Any] | None = None
    error: dict[str, str] | None = None
    transcript: list[dict[str, Any]] = field(default_factory=list)


class BandRunBroker:
    """Thread-safe bridge between the browser request and WebSocket agents."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._pending: dict[str, _PendingRun] = {}

    def register(self, run_id: str) -> None:
        with self._lock:
            if run_id in self._pending:
                raise ValueError(f"Band run {run_id!r} is already pending")
            self._pending[run_id] = _PendingRun()

    def cancel(self, run_id: str) -> None:
        with self._lock:
            self._pending.pop(run_id, None)

    def record(
        self,
        run_id: str,
        *,
        from_role: str,
        to_role: str,
        stage: str,
        message_id: str | None,
    ) -> None:
        entry = {
            "from": from_role.title(),
            "to": to_role.title(),
            "stage": stage,
            "message_id": message_id,
            "observed_at": _now(),
        }
        with self._lock:
            pending = self._pending.get(run_id)
            if pending is not None:
                if message_id and any(
                    item.get("message_id") == message_id
                    for item in pending.transcript
                ):
                    return
                pending.transcript.append(entry)

    def complete(
        self,
        run_id: str,
        result: Mapping[str, Any],
    ) -> None:
        with self._lock:
            pending = self._pending.get(run_id)
            if pending is None:
                return
            pending.result = dict(result)
            pending.event.set()

    def fail(self, run_id: str, error: Mapping[str, str]) -> None:
        with self._lock:
            pending = self._pending.get(run_id)
            if pending is None:
                return
            pending.error = dict(error)
            pending.event.set()

    def wait(
        self,
        run_id: str,
        timeout_seconds: float,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        with self._lock:
            pending = self._pending.get(run_id)
        if pending is None:
            raise RuntimeError("Band run was not registered")
        if not pending.event.wait(timeout_seconds):
            raise TimeoutError("Band agent collaboration timed out")
        with self._lock:
            pending = self._pending.pop(run_id, pending)
        if pending.error is not None:
            raise RuntimeError(pending.error.get("message", "Band agent failed"))
        if pending.result is None:
            raise RuntimeError("Band run completed without a result")
        return pending.result, list(pending.transcript)


class BandTools(Protocol):
    """Subset of the Band SDK room-bound tools used by deterministic agents."""

    async def send_message(
        self,
        content: str,
        mentions: list[str] | list[dict[str, str]] | None = None,
    ) -> Any:
        ...

    async def send_event(
        self,
        content: str,
        message_type: str,
        metadata: dict[str, Any] | None = None,
    ) -> Any:
        ...


class BandRoleHandler:
    """Run one role and transport its output to the next Band participant."""

    def __init__(
        self,
        role: str,
        configuration: BandConfiguration,
        broker: BandRunBroker,
    ) -> None:
        if role not in EXPECTED_STAGE:
            raise ValueError(f"Unknown Band role {role!r}")
        self.role = role
        self.configuration = configuration
        self.broker = broker

    async def handle(
        self,
        *,
        content: str,
        room_id: str,
        message_id: str | None,
        tools: BandTools,
    ) -> None:
        run_id: str | None = None
        try:
            envelope = parse_band_message(content)
            run_id = envelope.run_id
            if envelope.to_role != self.role:
                raise ValueError(
                    f"handoff addressed to {envelope.to_role!r}, not {self.role!r}"
                )
            if envelope.stage not in EXPECTED_STAGE[self.role]:
                raise ValueError(
                    f"role {self.role!r} cannot process stage {envelope.stage!r}"
                )

            self.broker.record(
                run_id,
                from_role=envelope.from_role,
                to_role=self.role,
                stage=envelope.stage,
                message_id=message_id,
            )
            if self.role == "coordinator":
                await self._coordinate_completion(envelope, room_id, tools)
            elif self.role == "scout":
                await self._run_scout(envelope, tools)
            elif self.role == "analyst":
                await self._run_analyst(envelope, tools)
            else:
                await self._run_coach(envelope, tools)
        except Exception as exc:
            error = _safe_error("band_role_error", f"{self.role} handoff failed")
            try:
                await tools.send_event(
                    content=error["message"],
                    message_type="error",
                    metadata={
                        "provider": PROVIDER,
                        "role": self.role,
                        "run_id": run_id or "unknown",
                        "code": error["code"],
                    },
                )
            except Exception:
                pass
            if run_id:
                if self.role == "coordinator":
                    self.broker.fail(run_id, error)
                else:
                    try:
                        await self._send(
                            tools,
                            BandEnvelope(
                                stage="error",
                                run_id=run_id,
                                from_role=self.role,
                                to_role="coordinator",
                                summary=error["message"],
                                payload={"error": error},
                            ),
                            "coordinator",
                        )
                    except Exception:
                        self.broker.fail(run_id, error)
            raise RuntimeError(error["message"]) from exc

    async def _send(
        self,
        tools: BandTools,
        envelope: BandEnvelope,
        target_role: str,
    ) -> None:
        target = self.configuration.identity(target_role)
        response = await tools.send_message(
            render_band_message(envelope, target_role.title()),
            mentions=[target.agent_id],
        )
        self.broker.record(
            envelope.run_id,
            from_role=envelope.from_role,
            to_role=target_role,
            stage=envelope.stage,
            message_id=_response_id(response),
        )

    async def _run_scout(
        self,
        envelope: BandEnvelope,
        tools: BandTools,
    ) -> None:
        from product.agents import run_scout

        profile = _mapping(envelope.payload.get("profile"), "profile")
        events = [
            _mapping(item, "event")
            for item in envelope.payload.get("events", [])
        ]
        scout = dict(run_scout(events, run_id=envelope.run_id))
        scout["integration_status"] = "connected"
        await tools.send_event(
            content=scout["summary"],
            message_type="task",
            metadata={
                "provider": PROVIDER,
                "role": "scout",
                "run_id": envelope.run_id,
                "candidate_count": len(events),
            },
        )
        await self._send(
            tools,
            BandEnvelope(
                stage="analyst_request",
                run_id=envelope.run_id,
                from_role="scout",
                to_role="analyst",
                summary=scout["summary"],
                payload={
                    "profile": profile,
                    "events": events,
                    "scout": scout,
                },
            ),
            "analyst",
        )

    async def _run_analyst(
        self,
        envelope: BandEnvelope,
        tools: BandTools,
    ) -> None:
        from product.agents import run_analyst

        profile = _mapping(envelope.payload.get("profile"), "profile")
        events = [
            _mapping(item, "event")
            for item in envelope.payload.get("events", [])
        ]
        scout = _mapping(envelope.payload.get("scout"), "scout")
        analyst = dict(
            run_analyst(
                profile,
                events,
                run_id=envelope.run_id,
            )
        )
        analyst["integration_status"] = "connected"
        recommendations = list(analyst["recommendations"])
        top = _mapping(recommendations[0], "recommendation")
        event = next(
            item for item in events if item.get("event_id") == top.get("event_id")
        )
        await tools.send_event(
            content=analyst["summary"],
            message_type="task",
            metadata={
                "provider": PROVIDER,
                "role": "analyst",
                "run_id": envelope.run_id,
                "top_event_id": top["event_id"],
            },
        )
        await self._send(
            tools,
            BandEnvelope(
                stage="coach_request",
                run_id=envelope.run_id,
                from_role="analyst",
                to_role="coach",
                summary=analyst["summary"],
                payload={
                    "profile": profile,
                    "event": event,
                    "recommendation": top,
                    "scout": scout,
                    "analyst": analyst,
                },
            ),
            "coach",
        )

    async def _run_coach(
        self,
        envelope: BandEnvelope,
        tools: BandTools,
    ) -> None:
        from product.agents import run_coach

        profile = _mapping(envelope.payload.get("profile"), "profile")
        event = _mapping(envelope.payload.get("event"), "event")
        recommendation = _mapping(
            envelope.payload.get("recommendation"),
            "recommendation",
        )
        scout = _mapping(envelope.payload.get("scout"), "scout")
        analyst = _mapping(envelope.payload.get("analyst"), "analyst")
        coach = dict(
            run_coach(
                profile,
                event,
                recommendation,
                run_id=envelope.run_id,
            )
        )
        coach["integration_status"] = "connected"
        result = {
            "run_id": envelope.run_id,
            "mode": "connected",
            "integration_status": "connected",
            "provider": PROVIDER,
            "status": "completed",
            "scout": scout,
            "analyst": analyst,
            "coach": coach,
            "handoffs": [scout["handoff"], analyst["handoff"]],
            "recommendations": analyst["recommendations"],
            "critique": coach["critique"],
            "mission": coach["mission"],
        }
        await tools.send_event(
            content=coach["summary"],
            message_type="task",
            metadata={
                "provider": PROVIDER,
                "role": "coach",
                "run_id": envelope.run_id,
                "event_id": event["event_id"],
            },
        )
        await self._send(
            tools,
            BandEnvelope(
                stage="complete",
                run_id=envelope.run_id,
                from_role="coach",
                to_role="coordinator",
                summary=coach["summary"],
                payload={"result": result},
            ),
            "coordinator",
        )

    async def _coordinate_completion(
        self,
        envelope: BandEnvelope,
        room_id: str,
        tools: BandTools,
    ) -> None:
        if envelope.stage == "error":
            raw_error = envelope.payload.get("error")
            error = (
                dict(raw_error)
                if isinstance(raw_error, Mapping)
                else _safe_error("band_agent_error", "Band specialist failed")
            )
            self.broker.fail(
                envelope.run_id,
                {
                    "code": str(error.get("code", "band_agent_error")),
                    "message": _safe_summary(error.get("message")),
                },
            )
            return

        result = envelope.payload.get("result")
        if not isinstance(result, Mapping):
            raise ValueError("Coach completion did not contain a result")
        await tools.send_event(
            content="Event Copilot Band collaboration completed.",
            message_type="task",
            metadata={
                "provider": PROVIDER,
                "role": "coordinator",
                "run_id": envelope.run_id,
                "room_id": room_id,
            },
        )
        self.broker.complete(envelope.run_id, result)


class BandRequestError(RuntimeError):
    """Sanitized Band Request API failure."""


class BandRequestClient:
    """Minimal Agent API client for Coordinator-owned room setup."""

    def __init__(
        self,
        configuration: BandConfiguration,
        *,
        request_json: Callable[
            [str, str, dict[str, Any] | None, float],
            dict[str, Any],
        ]
        | None = None,
    ) -> None:
        self.configuration = configuration
        self.identity = configuration.identity("coordinator")
        self._request_json = request_json or self._network_request

    @property
    def base_url(self) -> str:
        return f"{self.configuration.rest_url}/api/v1/agent"

    def _network_request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None,
        timeout_seconds: float,
    ) -> dict[str, Any]:
        body = (
            json.dumps(payload, separators=(",", ":")).encode("utf-8")
            if payload is not None
            else None
        )
        request = Request(
            f"{self.base_url}{path}",
            data=body,
            method=method,
            headers={
                "X-API-Key": self.identity.api_key,
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "event-copilot-band/1.0",
            },
        )
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                raw = response.read()
        except HTTPError as exc:
            raise BandRequestError(
                f"Band request failed with HTTP {exc.code}"
            ) from None
        except (URLError, TimeoutError, OSError):
            raise BandRequestError("Band request could not reach the provider") from None
        if not raw:
            return {}
        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError:
            raise BandRequestError("Band returned an invalid response") from None
        if not isinstance(decoded, Mapping):
            raise BandRequestError("Band returned an unexpected response")
        return dict(decoded)

    def request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._request_json(
            method,
            path,
            payload,
            self.configuration.timeout_seconds,
        )

    @staticmethod
    def _data(response: Mapping[str, Any]) -> Any:
        return response.get("data")

    def create_room(self) -> str:
        data = self._data(self.request("POST", "/chats", {"chat": {}}))
        if not isinstance(data, Mapping):
            raise BandRequestError("Band did not return a chat room")
        return _text(data.get("id"), "Band room ID")

    def add_participant(self, room_id: str, participant_id: str) -> None:
        self.request(
            "POST",
            f"/chats/{room_id}/participants",
            {
                "participant": {
                    "participant_id": participant_id,
                }
            },
        )

    def participants(self, room_id: str) -> list[dict[str, Any]]:
        data = self._data(
            self.request("GET", f"/chats/{room_id}/participants")
        )
        if not isinstance(data, Sequence) or isinstance(data, (str, bytes)):
            raise BandRequestError("Band did not return room participants")
        return [dict(item) for item in data if isinstance(item, Mapping)]

    def send_to_scout(
        self,
        room_id: str,
        message: str,
    ) -> str | None:
        scout = self.configuration.identity("scout")
        participant = next(
            (
                item
                for item in self.participants(room_id)
                if item.get("id") == scout.agent_id
            ),
            None,
        )
        if participant is None:
            raise BandRequestError("Scout is not present in the Band room")
        handle = participant.get("handle")
        if not isinstance(handle, str) or not handle.strip():
            raise BandRequestError("Scout has no mentionable Band handle")
        name = participant.get("name")
        if not isinstance(name, str) or not name.strip():
            raise BandRequestError("Scout has no Band display name")
        response = self.request(
            "POST",
            f"/chats/{room_id}/messages",
            {
                "message": {
                    "content": message,
                    "mentions": [
                        {
                            "id": scout.agent_id,
                            "handle": handle,
                            "name": name,
                        }
                    ],
                }
            },
        )
        return _response_id(self._data(response))


class BandSdkRuntime:
    """Own four Band SDK agents in one process with distinct identities."""

    def __init__(
        self,
        configuration: BandConfiguration,
        broker: BandRunBroker,
    ) -> None:
        self.configuration = configuration
        self.broker = broker
        self._ready = threading.Event()
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stop_signal: asyncio.Event | None = None
        self._agents: list[Any] = []
        self._startup_error: str | None = None
        self._lock = threading.Lock()

    def _build_adapter(self, role: str) -> Any:
        try:
            from band.core.simple_adapter import SimpleAdapter
        except ImportError as exc:
            raise RuntimeError(
                "Band SDK is not installed; install requirements-band.txt"
            ) from exc

        handler = BandRoleHandler(role, self.configuration, self.broker)

        class EventCopilotBandAdapter(SimpleAdapter[Any]):
            async def on_message(
                self,
                msg: Any,
                tools: Any,
                history: Any,
                participants_msg: str | None,
                contacts_msg: str | None,
                *,
                is_session_bootstrap: bool,
                room_id: str,
            ) -> None:
                del history, participants_msg, contacts_msg, is_session_bootstrap
                await handler.handle(
                    content=msg.content,
                    room_id=room_id,
                    message_id=getattr(msg, "id", None),
                    tools=tools,
                )

        return EventCopilotBandAdapter(history_converter=None)

    async def _async_main(self) -> None:
        try:
            from band import Agent

            self._stop_signal = asyncio.Event()
            self._agents = [
                Agent.create(
                    adapter=self._build_adapter(role),
                    agent_id=self.configuration.identity(role).agent_id,
                    api_key=self.configuration.identity(role).api_key,
                    ws_url=self.configuration.ws_url,
                    rest_url=self.configuration.rest_url,
                )
                for role in ROLE_ORDER
            ]
            started: list[Any] = []
            try:
                for agent in self._agents:
                    await agent.start()
                    started.append(agent)
                self._ready.set()
                await self._stop_signal.wait()
            finally:
                for agent in reversed(started):
                    try:
                        await agent.stop(timeout=5.0)
                    except Exception:
                        pass
        except Exception as exc:
            self._startup_error = _safe_summary(str(exc))
            self._ready.set()

    def _thread_main(self) -> None:
        loop = asyncio.new_event_loop()
        self._loop = loop
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._async_main())
        finally:
            self._loop = None
            loop.close()

    def start(self) -> None:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._ready.clear()
            self._startup_error = None
            self._thread = threading.Thread(
                target=self._thread_main,
                name="event-copilot-band",
                daemon=True,
            )
            self._thread.start()
        if not self._ready.wait(self.configuration.startup_timeout_seconds):
            raise TimeoutError("Band SDK agents did not become ready")
        if self._startup_error:
            raise RuntimeError(self._startup_error)

    def close(self) -> None:
        loop = self._loop
        signal = self._stop_signal
        thread = self._thread
        if loop is not None and signal is not None and loop.is_running():
            loop.call_soon_threadsafe(signal.set)
        if (
            thread is not None
            and thread.is_alive()
            and thread is not threading.current_thread()
        ):
            thread.join(timeout=8.0)


class BandOrchestrator:
    """UI-facing connected Band adapter with deterministic fallback."""

    def __init__(
        self,
        fallback: Fallback,
        *,
        configuration: BandConfiguration | None = None,
        request_client: BandRequestClient | None = None,
        runtime: BandSdkRuntime | None = None,
        broker: BandRunBroker | None = None,
    ) -> None:
        self.fallback = fallback
        self.configuration = configuration or BandConfiguration.from_environment()
        self.broker = broker or BandRunBroker()
        self.request_client = request_client
        self.runtime = runtime

    def _fallback_result(
        self,
        profile: Record,
        events: Sequence[Record],
        run_id: str,
        *,
        band_mode: str,
        band_status: str,
        error: dict[str, str] | None = None,
        missing_fields: Sequence[str] = (),
    ) -> dict[str, Any]:
        result = dict(self.fallback(profile, events, run_id))
        result["mode"] = "demo_fallback"
        result["integration_status"] = "demo_fallback"
        band: dict[str, Any] = {
            "provider": PROVIDER,
            "mode": band_mode,
            "status": band_status,
            "timestamp": _now(),
            "room_id": None,
            "transcript": [],
        }
        if error is not None:
            band["error"] = error
        if missing_fields:
            band["missing_configuration"] = list(missing_fields)
        result["band"] = band
        return result

    def coordinate(
        self,
        profile: Record,
        events: Sequence[Record],
        run_id: str,
    ) -> dict[str, Any]:
        """Coordinate one real Band room or return the direct local fallback."""

        run_id = _text(run_id, "run_id")
        event_values = list(events)
        if not self.configuration.enabled:
            return self._fallback_result(
                profile,
                event_values,
                run_id,
                band_mode="disabled",
                band_status="Band disabled; direct role functions used",
            )

        missing = self.configuration.missing_fields()
        if missing:
            return self._fallback_result(
                profile,
                event_values,
                run_id,
                band_mode="disabled",
                band_status="Band configuration incomplete; direct role functions used",
                missing_fields=missing,
            )

        started_at = _now()
        started = monotonic()
        self.broker.register(run_id)
        try:
            if self.runtime is None:
                self.runtime = BandSdkRuntime(self.configuration, self.broker)
            self.runtime.start()
            if self.request_client is None:
                self.request_client = BandRequestClient(self.configuration)

            room_id = self.request_client.create_room()
            for role in ("scout", "analyst", "coach"):
                self.request_client.add_participant(
                    room_id,
                    self.configuration.identity(role).agent_id,
                )

            envelope = BandEnvelope(
                stage="scout_request",
                run_id=run_id,
                from_role="coordinator",
                to_role="scout",
                summary=(
                    "Validate these grounded event candidates, then hand the "
                    "candidate set to Analyst."
                ),
                payload={
                    "profile": _mapping(profile, "profile"),
                    "events": [
                        _mapping(event, "event") for event in event_values
                    ],
                },
            )
            initial_message_id = self.request_client.send_to_scout(
                room_id,
                render_band_message(envelope, "Scout"),
            )
            self.broker.record(
                run_id,
                from_role="coordinator",
                to_role="scout",
                stage="scout_request",
                message_id=initial_message_id,
            )
            result, transcript = self.broker.wait(
                run_id,
                self.configuration.timeout_seconds,
            )
            result.update(
                {
                    "provider": PROVIDER,
                    "status": "completed",
                    "mode": "connected",
                    "integration_status": "connected",
                    "started_at": started_at,
                    "finished_at": _now(),
                    "band": {
                        "provider": PROVIDER,
                        "status": "completed",
                        "mode": "connected",
                        "room_id": room_id,
                        "transport": "REST + WebSocket",
                        "routing": "@mention",
                        "elapsed_ms": round((monotonic() - started) * 1000),
                        "transcript": transcript,
                    },
                }
            )
            return result
        except TimeoutError:
            self.broker.cancel(run_id)
            return self._fallback_result(
                profile,
                event_values,
                run_id,
                band_mode="error",
                band_status="Band timed out; direct role functions used",
                error=_safe_error("band_timeout", "Band collaboration timed out"),
            )
        except Exception:
            self.broker.cancel(run_id)
            return self._fallback_result(
                profile,
                event_values,
                run_id,
                band_mode="error",
                band_status="Band unavailable; direct role functions used",
                error=_safe_error(
                    "band_adapter_error",
                    "Band collaboration failed; provider details withheld",
                ),
            )

    def close(self) -> None:
        if self.runtime is not None:
            self.runtime.close()
