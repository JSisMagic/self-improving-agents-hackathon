"""Grounded Event Mission rendering and cited.md publication boundary.

The module is deliberately provider-agnostic.  A connected cited.md client can
be injected for the final demo; without one, callers receive the exact local
Markdown preview with a truthful ``demo_fallback`` mode.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime, timezone
import hashlib
import inspect
from typing import Any, Protocol
from urllib.parse import urlsplit


DEFAULT_PROVIDER = "cited.md"
DEFAULT_TIMEOUT_SECONDS = 5.0
VALID_MODES = {"connected", "demo_fallback", "disabled", "error"}


class PublisherAdapter(Protocol):
    """Small adapter surface for a connected cited.md implementation."""

    provider: str

    def publish_markdown(
        self,
        markdown: str,
        *,
        timeout_seconds: float,
    ) -> Mapping[str, Any]:
        """Publish *markdown* and return an inspectable identifier or URL."""


@dataclass(frozen=True, slots=True)
class PublicationResult:
    """Normalized, safe-to-display publication outcome."""

    provider: str
    status: str
    mode: str
    timestamp: str
    local_content: str
    remote_id: str | None = None
    remote_url: str | None = None
    payload: dict[str, Any] | None = None
    error: dict[str, str] | None = None

    def __post_init__(self) -> None:
        if self.mode not in VALID_MODES:
            raise ValueError(f"unsupported publication mode: {self.mode}")

    @property
    def remote_identifier(self) -> str | None:
        """Compatibility alias for consumers that use the spec wording."""

        return self.remote_id

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable envelope."""

        return asdict(self)


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


def _single_line(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split())


def _absolute_url(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    parsed = urlsplit(candidate)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return candidate
    return None


def _safe_remote_url(value: Any) -> str | None:
    """Keep an inspectable remote URL while dropping credentials and tokens."""

    url = _absolute_url(value)
    if url is None:
        return None
    parsed = urlsplit(url)
    if parsed.username or parsed.password:
        return None
    return parsed._replace(query="", fragment="").geturl()


def render_event_mission_markdown(
    mission: Mapping[str, Any] | Any,
    event: Mapping[str, Any] | Any | None = None,
) -> str:
    """Render readable mission Markdown while preserving claim-level URLs.

    Citations come only from the mission.  Missing or malformed citations are
    rejected instead of being replaced with an invented source.
    """

    mission_data = _to_mapping(mission, name="mission")
    event_data = _to_mapping(event, name="event") if event is not None else {}

    event_id = _single_line(mission_data.get("event_id", "")).strip()
    title = _single_line(event_data.get("title", "")).strip() or event_id
    if not title:
        raise ValueError("mission must identify an event")

    objectives = mission_data.get("objectives")
    targets = mission_data.get("target_people")
    questions = mission_data.get("questions_to_ask")
    follow_up = _single_line(mission_data.get("follow_up_plan", "")).strip()
    citations = mission_data.get("citations")

    if not isinstance(objectives, list) or not objectives:
        raise ValueError("mission must contain at least one objective")
    if not isinstance(targets, list) or not targets:
        raise ValueError("mission must contain at least one target person or role")
    if not isinstance(questions, list) or not questions:
        raise ValueError("mission must contain at least one question")
    if not follow_up:
        raise ValueError("mission must contain a follow-up plan")
    if not isinstance(citations, list) or not citations:
        raise ValueError("mission must contain at least one claim-level citation")

    rendered_objectives: list[str] = []
    for objective in objectives:
        objective_data = _to_mapping(objective, name="objective")
        metric = _single_line(objective_data.get("metric", "")).strip()
        target = objective_data.get("target")
        rationale = _single_line(objective_data.get("rationale", "")).strip()
        if not metric or not isinstance(target, (int, float)) or isinstance(target, bool):
            raise ValueError("each objective must contain a metric and numeric target")
        if not rationale:
            raise ValueError("each objective must contain a rationale")
        rendered_objectives.append(f"- **{metric}:** {target:g} — {rationale}")

    rendered_targets = [
        f"- {_single_line(target).strip()}"
        for target in targets
        if _single_line(target).strip()
    ]
    rendered_questions = [
        f"- {_single_line(question).strip()}"
        for question in questions
        if _single_line(question).strip()
    ]
    if not rendered_targets or not rendered_questions:
        raise ValueError("mission targets and questions cannot be blank")

    rendered_citations: list[str] = []
    for citation in citations:
        citation_data = _to_mapping(citation, name="citation")
        claim = _single_line(citation_data.get("claim", "")).strip()
        url = _absolute_url(citation_data.get("url"))
        if not claim or url is None:
            raise ValueError("each citation must contain a claim and absolute HTTP(S) URL")
        rendered_citations.append(f"- {claim}: <{url}>")

    metadata: list[str] = []
    for label, key in (
        ("Mission", "mission_id"),
        ("Event", "event_id"),
        ("Recommendation run", "recommendation_run_id"),
        ("Created", "created_at"),
    ):
        value = _single_line(mission_data.get(key, "")).strip()
        if value:
            metadata.append(f"- **{label}:** {value}")

    sections = [
        f"# Event Mission: {title}",
        "\n".join(metadata),
        "## Objectives\n\n" + "\n".join(rendered_objectives),
        "## Target people or roles\n\n" + "\n".join(rendered_targets),
        "## Questions to ask\n\n" + "\n".join(rendered_questions),
        f"## Follow-up plan\n\n{follow_up}",
        "## Sources\n\n" + "\n".join(rendered_citations),
    ]
    return "\n\n".join(section for section in sections if section).rstrip() + "\n"


def _adapter_target(adapter: Any) -> Callable[..., Any]:
    for name in ("publish_markdown", "publish"):
        target = getattr(adapter, name, None)
        if callable(target):
            return target
    if callable(adapter):
        return adapter
    raise TypeError("publisher adapter must be callable or expose publish_markdown()")


def _invoke_adapter(
    adapter: Any,
    markdown: str,
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
        return target(markdown, timeout_seconds=timeout_seconds)
    return target(markdown)


def _call_bounded(adapter: Any, markdown: str, timeout_seconds: float) -> Any:
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="cited-publisher")
    future = executor.submit(_invoke_adapter, adapter, markdown, timeout_seconds)
    try:
        return future.result(timeout=timeout_seconds)
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def _adapter_provider(adapter: Any, response: Mapping[str, Any] | None = None) -> str:
    if response is not None:
        response_provider = response.get("provider")
        if isinstance(response_provider, str) and response_provider.strip():
            return response_provider.strip()
    adapter_provider = getattr(adapter, "provider", None)
    if isinstance(adapter_provider, str) and adapter_provider.strip():
        return adapter_provider.strip()
    return DEFAULT_PROVIDER


def publish_markdown(
    markdown: str,
    *,
    adapter: PublisherAdapter | Callable[..., Mapping[str, Any]] | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> PublicationResult:
    """Publish exact Markdown through an injected adapter or return a preview.

    This function performs no network call on its own.  Connected success is
    reported only when the adapter returns an inspectable remote ID or URL.
    Raw provider exceptions and response bodies are never copied into results.
    """

    timestamp = _utc_timestamp()
    if not isinstance(markdown, str) or not markdown.strip():
        return PublicationResult(
            provider=DEFAULT_PROVIDER,
            status="error",
            mode="error",
            timestamp=timestamp,
            local_content=markdown if isinstance(markdown, str) else "",
            error={
                "code": "invalid_markdown",
                "message": "Publication content must be non-empty Markdown.",
            },
        )
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be greater than zero")

    local_payload = {
        "content_length": len(markdown),
        "content_sha256": hashlib.sha256(markdown.encode("utf-8")).hexdigest(),
    }
    if adapter is None:
        return PublicationResult(
            provider=DEFAULT_PROVIDER,
            status="preview",
            mode="demo_fallback",
            timestamp=timestamp,
            local_content=markdown,
            payload=local_payload,
        )

    try:
        response = _call_bounded(adapter, markdown, timeout_seconds)
    except FutureTimeout:
        return PublicationResult(
            provider=_adapter_provider(adapter),
            status="error",
            mode="error",
            timestamp=timestamp,
            local_content=markdown,
            payload=local_payload,
            error={
                "code": "adapter_timeout",
                "message": "Publication adapter timed out.",
            },
        )
    except Exception:
        return PublicationResult(
            provider=_adapter_provider(adapter),
            status="error",
            mode="error",
            timestamp=timestamp,
            local_content=markdown,
            payload=local_payload,
            error={
                "code": "adapter_error",
                "message": "Publication adapter failed; local preview remains available.",
            },
        )

    if not isinstance(response, Mapping):
        return PublicationResult(
            provider=_adapter_provider(adapter),
            status="error",
            mode="error",
            timestamp=timestamp,
            local_content=markdown,
            payload=local_payload,
            error={
                "code": "invalid_adapter_response",
                "message": "Publication adapter returned no inspectable result.",
            },
        )

    provider = _adapter_provider(adapter, response)
    response_status = str(response.get("status", "")).strip().lower()
    if response_status in {"error", "failed", "failure"}:
        return PublicationResult(
            provider=provider,
            status="error",
            mode="error",
            timestamp=timestamp,
            local_content=markdown,
            payload=local_payload,
            error={
                "code": "provider_rejected",
                "message": "Publication provider did not confirm publication.",
            },
        )

    remote_id_value = (
        response.get("remote_id")
        or response.get("remote_identifier")
        or response.get("id")
    )
    remote_id = (
        str(remote_id_value).strip()
        if remote_id_value is not None and str(remote_id_value).strip()
        else None
    )
    remote_url = _safe_remote_url(response.get("remote_url") or response.get("url"))
    if remote_id is None and remote_url is None:
        return PublicationResult(
            provider=provider,
            status="error",
            mode="error",
            timestamp=timestamp,
            local_content=markdown,
            payload=local_payload,
            error={
                "code": "missing_remote_evidence",
                "message": "Publication adapter returned no remote identifier or URL.",
            },
        )

    return PublicationResult(
        provider=provider,
        status="published",
        mode="connected",
        timestamp=timestamp,
        local_content=markdown,
        remote_id=remote_id,
        remote_url=remote_url,
        payload=local_payload,
    )


def publish_mission(
    mission: Mapping[str, Any] | Any,
    event: Mapping[str, Any] | Any | None = None,
    *,
    adapter: PublisherAdapter | Callable[..., Mapping[str, Any]] | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> PublicationResult:
    """Render and publish a mission through the normalized boundary."""

    markdown = render_event_mission_markdown(mission, event)
    return publish_markdown(
        markdown,
        adapter=adapter,
        timeout_seconds=timeout_seconds,
    )
