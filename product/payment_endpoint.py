"""Framework-free x402 playbook boundary.

No network or payment action occurs unless a caller injects an adapter and
explicitly enables payments.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime, timezone
import inspect
import os
from queue import Empty, Queue
from threading import Thread
from typing import Any, Protocol
from urllib.parse import urlsplit, urlunsplit


PLAYBOOK_ROUTE = "/api/events/{event_id}/playbook"
DEFAULT_PROVIDER = "x402"
DEFAULT_TIMEOUT_SECONDS = 5.0
VALID_MODES = {"connected", "demo_fallback", "disabled", "error"}
CONNECTED_STATUSES = {"payment_required", "verified", "settled", "failed"}
_TESTNET_MARKERS = ("testnet", "sepolia", "devnet")


class AdapterTimeout(TimeoutError):
    """Raised when a provider adapter exceeds its caller-visible deadline."""


class PaymentAdapter(Protocol):
    """Small adapter surface for an injected x402 testnet implementation."""

    provider: str
    network: str

    def authorize_playbook(
        self,
        request: Mapping[str, Any],
        *,
        timeout_seconds: float,
    ) -> Mapping[str, Any]:
        """Return a normalized x402 status without exposing credentials."""


@dataclass(frozen=True, slots=True)
class PlaybookResult:
    """Safe-to-display detailed-playbook payment decision."""

    provider: str
    status: str
    mode: str
    payment_mode: str
    timestamp: str
    event_id: str
    playbook: dict[str, Any] | None = None
    payment: dict[str, Any] | None = None
    error: dict[str, str] | None = None

    def __post_init__(self) -> None:
        if self.mode not in VALID_MODES:
            raise ValueError(f"unsupported payment mode: {self.mode}")
        allowed_statuses = CONNECTED_STATUSES | {"disabled", "demo_fallback", "error"}
        if self.status not in allowed_statuses:
            raise ValueError(f"unsupported payment status: {self.status}")

    @property
    def payload(self) -> dict[str, Any] | None:
        """INT-001 payload alias for consumers using the generic envelope."""

        return self.playbook if self.playbook is not None else self.payment

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable envelope."""

        result = asdict(self)
        result["payload"] = self.payload
        return result


# INT-001 calls the normalized output a PaymentDecision.
PaymentDecision = PlaybookResult


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _to_mapping(value: Any, *, name: str) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    if hasattr(value, "to_dict"):
        converted = value.to_dict()
        if isinstance(converted, Mapping):
            return converted
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    raise TypeError(f"{name} must be a mapping or expose to_dict()")


def _enabled_from_environment() -> bool:
    return os.getenv("PAYMENTS_ENABLED", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _single_line(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split())


def _safe_public_url(value: Any) -> str | None:
    """Return an inspectable HTTP(S) URL without credentials or query tokens."""

    if not isinstance(value, str):
        return None
    candidate = value.strip()
    parsed = urlsplit(candidate)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.username
        or parsed.password
    ):
        return None
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))


def _playbook_from_mission(
    event_id: str,
    mission: Mapping[str, Any] | Any,
) -> dict[str, Any]:
    mission_data = _to_mapping(mission, name="mission")
    mission_event_id = _single_line(mission_data.get("event_id", "")).strip()
    if not event_id or not mission_event_id or mission_event_id != event_id:
        raise ValueError("mission event_id must match the requested event")

    target_people = mission_data.get("target_people")
    questions = mission_data.get("questions_to_ask")
    objectives = mission_data.get("objectives")
    follow_up = _single_line(mission_data.get("follow_up_plan", "")).strip()
    if not isinstance(target_people, list) or not target_people:
        raise ValueError("mission must contain target_people")
    if not isinstance(questions, list) or not questions:
        raise ValueError("mission must contain questions_to_ask")
    if not isinstance(objectives, list) or not objectives:
        raise ValueError("mission must contain objectives")
    if not follow_up:
        raise ValueError("mission must contain follow_up_plan")

    normalized_objectives: list[dict[str, Any]] = []
    for objective in objectives:
        objective_data = _to_mapping(objective, name="objective")
        metric = _single_line(objective_data.get("metric", "")).strip()
        target = objective_data.get("target")
        rationale = _single_line(objective_data.get("rationale", "")).strip()
        if (
            not metric
            or not isinstance(target, (int, float))
            or isinstance(target, bool)
            or not rationale
        ):
            raise ValueError("mission contains an invalid objective")
        normalized_objectives.append(
            {
                "metric": metric,
                "target": target,
                "rationale": rationale,
            }
        )

    normalized_targets = [
        _single_line(value).strip()
        for value in target_people
        if _single_line(value).strip()
    ]
    normalized_questions = [
        _single_line(value).strip()
        for value in questions
        if _single_line(value).strip()
    ]
    if not normalized_targets or not normalized_questions:
        raise ValueError("mission target people and questions cannot be blank")

    return {
        "event_id": event_id,
        "target_people": normalized_targets,
        "questions": normalized_questions,
        "objectives": normalized_objectives,
        "follow_up_strategy": follow_up,
    }


def _adapter_target(adapter: Any) -> Callable[..., Any]:
    for name in ("authorize_playbook", "authorize"):
        target = getattr(adapter, name, None)
        if callable(target):
            return target
    if callable(adapter):
        return adapter
    raise TypeError("payment adapter must be callable or expose authorize_playbook()")


def _invoke_adapter(
    adapter: Any,
    request: Mapping[str, Any],
    timeout_seconds: float,
) -> Any:
    target = _adapter_target(adapter)
    try:
        parameters = inspect.signature(target).parameters.values()
    except (TypeError, ValueError):
        parameters = ()
    accepts_timeout = any(
        parameter.name == "timeout_seconds"
        or parameter.kind is inspect.Parameter.VAR_KEYWORD
        for parameter in parameters
    )
    if accepts_timeout:
        return target(request, timeout_seconds=timeout_seconds)
    return target(request)


def _call_bounded(
    adapter: Any,
    request: Mapping[str, Any],
    timeout_seconds: float,
) -> Any:
    outcome: Queue[tuple[bool, Any]] = Queue(maxsize=1)

    def invoke() -> None:
        try:
            outcome.put((True, _invoke_adapter(adapter, request, timeout_seconds)))
        except Exception as exc:
            outcome.put((False, exc))

    worker = Thread(
        target=invoke,
        name="x402-payment",
        daemon=True,
    )
    worker.start()
    try:
        succeeded, value = outcome.get(timeout=timeout_seconds)
    except Empty as exc:
        raise AdapterTimeout from exc
    if not succeeded:
        raise value
    return value


def _provider_name(adapter: Any, response: Mapping[str, Any] | None = None) -> str:
    if response is not None:
        value = response.get("provider")
        if isinstance(value, str) and value.strip():
            return value.strip()
    value = getattr(adapter, "provider", None)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return DEFAULT_PROVIDER


def _testnet_network(
    adapter: Any,
    response: Mapping[str, Any],
) -> str | None:
    value = response.get("network") or getattr(adapter, "network", None)
    if not isinstance(value, str):
        return None
    network = value.strip()
    if any(marker in network.lower() for marker in _TESTNET_MARKERS):
        return network
    return None


def _safe_payment_evidence(
    response: Mapping[str, Any],
    network: str,
) -> dict[str, Any]:
    evidence: dict[str, Any] = {"network": network}
    for key in ("request_id", "verification_id", "transaction_id"):
        value = response.get(key)
        if isinstance(value, (str, int)) and str(value).strip():
            evidence[key] = str(value).strip()
    for key in ("payment_url", "receipt_url"):
        value = _safe_public_url(response.get(key))
        if value is not None:
            evidence[key] = value
    amount = response.get("amount")
    if isinstance(amount, (int, float)) and not isinstance(amount, bool) and amount >= 0:
        evidence["amount"] = amount
    currency = response.get("currency")
    if isinstance(currency, str) and 0 < len(currency.strip()) <= 16:
        evidence["currency"] = currency.strip()
    return evidence


def _payment_error(
    *,
    event_id: str,
    provider: str,
    code: str,
    message: str,
) -> PlaybookResult:
    return PlaybookResult(
        provider=provider,
        status="error",
        mode="error",
        payment_mode="x402_testnet",
        timestamp=_utc_timestamp(),
        event_id=event_id,
        error={"code": code, "message": message},
    )


def request_playbook(
    event_id: str,
    mission: Mapping[str, Any] | Any,
    *,
    adapter: PaymentAdapter | Callable[..., Mapping[str, Any]] | None = None,
    payments_enabled: bool | None = None,
    payment_context: Mapping[str, Any] | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> PlaybookResult:
    """Return demo content or authorize access through an injected x402 adapter."""

    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be greater than zero")
    try:
        playbook = _playbook_from_mission(event_id, mission)
    except (TypeError, ValueError):
        return _payment_error(
            event_id=event_id,
            provider=DEFAULT_PROVIDER,
            code="invalid_playbook_request",
            message="The requested event and mission do not form a valid playbook.",
        )

    if payments_enabled is not None and not isinstance(payments_enabled, bool):
        raise TypeError("payments_enabled must be a boolean or None")
    enabled = _enabled_from_environment() if payments_enabled is None else payments_enabled
    timestamp = _utc_timestamp()
    if not enabled:
        return PlaybookResult(
            provider=DEFAULT_PROVIDER,
            status="disabled",
            mode="disabled",
            payment_mode="demo",
            timestamp=timestamp,
            event_id=event_id,
            playbook=playbook,
        )
    if adapter is None:
        return PlaybookResult(
            provider=DEFAULT_PROVIDER,
            status="demo_fallback",
            mode="demo_fallback",
            payment_mode="demo",
            timestamp=timestamp,
            event_id=event_id,
            playbook=playbook,
            error={
                "code": "adapter_unavailable",
                "message": "No x402 testnet adapter is connected; demo content is shown.",
            },
        )

    request: dict[str, Any] = {
        "event_id": event_id,
        "resource": PLAYBOOK_ROUTE.format(event_id=event_id),
    }
    if payment_context is not None:
        request["payment_context"] = dict(payment_context)

    try:
        response = _call_bounded(adapter, request, timeout_seconds)
    except AdapterTimeout:
        return _payment_error(
            event_id=event_id,
            provider=_provider_name(adapter),
            code="adapter_timeout",
            message="Payment adapter timed out; no transaction was confirmed.",
        )
    except Exception:
        return _payment_error(
            event_id=event_id,
            provider=_provider_name(adapter),
            code="adapter_error",
            message="Payment adapter failed; no transaction was confirmed.",
        )

    if not isinstance(response, Mapping):
        return _payment_error(
            event_id=event_id,
            provider=_provider_name(adapter),
            code="invalid_adapter_response",
            message="Payment adapter returned no inspectable decision.",
        )

    provider = _provider_name(adapter, response)
    status = str(response.get("status", "")).strip().lower()
    if status not in CONNECTED_STATUSES:
        return _payment_error(
            event_id=event_id,
            provider=provider,
            code="unknown_payment_status",
            message="Payment adapter returned an unsupported status.",
        )

    network = _testnet_network(adapter, response)
    if network is None:
        return _payment_error(
            event_id=event_id,
            provider=provider,
            code="testnet_not_confirmed",
            message="Payment adapter did not confirm a testnet network.",
        )

    evidence = _safe_payment_evidence(response, network)
    inspectable_keys = {
        "request_id",
        "verification_id",
        "transaction_id",
        "payment_url",
        "receipt_url",
    }
    if status != "failed" and not inspectable_keys.intersection(evidence):
        return _payment_error(
            event_id=event_id,
            provider=provider,
            code="missing_payment_evidence",
            message="Payment adapter returned no inspectable testnet evidence.",
        )

    return PlaybookResult(
        provider=provider,
        status=status,
        mode="connected",
        payment_mode="x402_testnet",
        timestamp=timestamp,
        event_id=event_id,
        playbook=playbook if status in {"verified", "settled"} else None,
        payment=evidence,
        error=(
            {
                "code": "payment_failed",
                "message": "The testnet payment was not authorized.",
            }
            if status == "failed"
            else None
        ),
    )


def get_playbook(
    event_id: str,
    mission: Mapping[str, Any] | Any,
    *,
    adapter: PaymentAdapter | Callable[..., Mapping[str, Any]] | None = None,
    payments_enabled: bool | None = None,
    payment_context: Mapping[str, Any] | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> PlaybookResult:
    """Direct-call handler for ``GET /api/events/{event_id}/playbook``."""

    return request_playbook(
        event_id,
        mission,
        adapter=adapter,
        payments_enabled=payments_enabled,
        payment_context=payment_context,
        timeout_seconds=timeout_seconds,
    )


def authorize_playbook(
    request: Mapping[str, Any],
    *,
    adapter: PaymentAdapter | Callable[..., Mapping[str, Any]] | None = None,
    payments_enabled: bool | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> PaymentDecision:
    """INT-001 request-envelope form of :func:`request_playbook`."""

    request_data = _to_mapping(request, name="request")
    event_id = _single_line(request_data.get("event_id", "")).strip()
    mission = request_data.get("mission")
    payment_context = request_data.get("payment_context")
    if not isinstance(payment_context, Mapping):
        payment_context = None
    return request_playbook(
        event_id,
        mission,
        adapter=adapter,
        payments_enabled=payments_enabled,
        payment_context=payment_context,
        timeout_seconds=timeout_seconds,
    )
