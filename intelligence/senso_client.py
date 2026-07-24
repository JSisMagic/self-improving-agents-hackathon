"""On-demand event-page crawling with optional Senso source ingestion.

Senso is the grounded context layer, not the HTTP crawler.  This adapter fetches
the requested event pages at call time, extracts schema.org ``Event`` JSON-LD,
and uploads a Markdown snapshot to Senso when ``SENSO_API_KEY`` is configured.
The returned integration mode never presents a local-only crawl as connected
Senso behavior.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import ipaddress
import json
import os
import re
import socket
import ssl
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

from shared.contracts import Event

from .event_extractor import normalize_event


DEFAULT_BASE_URL = "https://apiv2.senso.ai/api/v1"
DEFAULT_MAX_RESPONSE_BYTES = 2_000_000
SENSO_CLI_USER_AGENT = "senso-cli/0.11.1"
SUPPORTED_CONTENT_TYPES = {
    "application/json",
    "application/ld+json",
    "application/xhtml+xml",
    "text/html",
}


class SensoUnavailable(RuntimeError):
    """Raised when a live page or connected Senso operation cannot complete."""


@dataclass(slots=True, frozen=True)
class HttpResponse:
    status: int
    headers: Mapping[str, str]
    body: bytes


@dataclass(slots=True)
class EventCrawlResult:
    provider: str
    status: str
    mode: str
    timestamp: str
    events: list[Event]
    crawled_urls: list[str]
    senso_content_ids: list[str]
    errors: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["events"] = [event.to_dict() for event in self.events]
        return payload


HttpRequest = Callable[
    [str, str, Mapping[str, str], bytes | None, float],
    HttpResponse,
]


class _JsonLdParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._in_json_ld = False
        self._parts: list[str] = []
        self.documents: list[str] = []
        self.text_parts: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        attributes = {
            key.casefold(): (value or "")
            for key, value in attrs
        }
        if (
            tag.casefold() == "script"
            and attributes.get("type", "").split(";", 1)[0].strip().casefold()
            == "application/ld+json"
        ):
            self._in_json_ld = True
            self._parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() == "script" and self._in_json_ld:
            self.documents.append("".join(self._parts))
            self._in_json_ld = False
            self._parts = []

    def handle_data(self, data: str) -> None:
        if self._in_json_ld:
            self._parts.append(data)
        elif data.strip():
            self.text_parts.append(data.strip())


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_error(exc: BaseException, api_key: str | None = None) -> str:
    message = " ".join(str(exc).split())[:240] or type(exc).__name__
    if api_key:
        message = message.replace(api_key, "[redacted]")
    return message


def _validate_source_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise SensoUnavailable("event source must be an absolute HTTP(S) URL")
    hostname = parsed.hostname.casefold().rstrip(".")
    if hostname == "localhost" or hostname.endswith(".localhost") or hostname.endswith(".local"):
        raise SensoUnavailable("local event-source hosts are not allowed")
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        return url
    if not address.is_global:
        raise SensoUnavailable("private or non-global event-source addresses are not allowed")
    return url


def _validate_resolved_host(url: str) -> None:
    hostname = urlparse(url).hostname
    if not hostname:
        raise SensoUnavailable("event source has no hostname")
    try:
        addresses = {
            item[4][0]
            for item in socket.getaddrinfo(hostname, None)
        }
    except socket.gaierror as exc:
        raise SensoUnavailable("event-source hostname could not be resolved") from exc
    if not addresses:
        raise SensoUnavailable("event-source hostname resolved to no addresses")
    for raw_address in addresses:
        try:
            address = ipaddress.ip_address(raw_address)
        except ValueError as exc:
            raise SensoUnavailable("event-source hostname resolved unexpectedly") from exc
        if not address.is_global:
            raise SensoUnavailable(
                "event-source hostname resolved to a private or non-global address"
            )


def _default_http_request(
    method: str,
    url: str,
    headers: Mapping[str, str],
    data: bytes | None,
    timeout_seconds: float,
) -> HttpResponse:
    request = Request(url, data=data, headers=dict(headers), method=method)
    ca_file = os.getenv("SSL_CERT_FILE")
    if not ca_file and Path("/etc/ssl/cert.pem").is_file():
        ca_file = "/etc/ssl/cert.pem"
    context = ssl.create_default_context(cafile=ca_file)
    try:
        with urlopen(
            request,
            timeout=timeout_seconds,
            context=context,
        ) as response:
            body = response.read(DEFAULT_MAX_RESPONSE_BYTES + 1)
            if len(body) > DEFAULT_MAX_RESPONSE_BYTES:
                raise SensoUnavailable("response exceeded the 2 MB safety limit")
            return HttpResponse(
                status=int(getattr(response, "status", 200)),
                headers=dict(response.headers.items()),
                body=body,
            )
    except HTTPError as exc:
        raise SensoUnavailable(f"HTTP {exc.code} from remote service") from exc
    except (URLError, TimeoutError, socket.timeout, OSError) as exc:
        raise SensoUnavailable(f"remote service unavailable: {exc}") from exc


def _iter_json_objects(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        graph = value.get("@graph")
        if isinstance(graph, list):
            for item in graph:
                yield from _iter_json_objects(item)
    elif isinstance(value, list):
        for item in value:
            yield from _iter_json_objects(item)


def _is_event(document: Mapping[str, Any]) -> bool:
    kind = document.get("@type")
    kinds = kind if isinstance(kind, list) else [kind]
    return any(
        isinstance(item, str) and item.casefold().endswith("event")
        for item in kinds
    )


def _plain_text(value: Any) -> str:
    if value is None:
        return ""
    parser = _JsonLdParser()
    parser.feed(html.unescape(str(value)))
    text = " ".join(parser.text_parts)
    return re.sub(r"\s+", " ", text).strip()


def _location(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        rendered = [_location(item) for item in value]
        return "; ".join(item for item in rendered if item)
    if not isinstance(value, Mapping):
        return ""

    parts: list[str] = []
    name = value.get("name")
    if isinstance(name, str) and name.strip():
        parts.append(name.strip())
    address = value.get("address")
    if isinstance(address, str) and address.strip():
        parts.append(address.strip())
    elif isinstance(address, Mapping):
        for key in (
            "streetAddress",
            "addressLocality",
            "addressRegion",
            "postalCode",
            "addressCountry",
        ):
            item = address.get(key)
            if isinstance(item, str) and item.strip():
                parts.append(item.strip())
    url = value.get("url")
    if not parts and isinstance(url, str) and url.strip():
        parts.append(url.strip())
    return ", ".join(dict.fromkeys(parts))


def _keywords(value: Any) -> list[str]:
    if isinstance(value, str):
        return [
            item.strip()
            for item in re.split(r"[,;|]", value)
            if item.strip()
        ]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _price(value: Any) -> float:
    offers = value if isinstance(value, list) else [value]
    prices: list[float] = []
    for offer in offers:
        if not isinstance(offer, Mapping):
            continue
        raw = offer.get("price", offer.get("lowPrice"))
        try:
            prices.append(max(0.0, float(raw)))
        except (TypeError, ValueError):
            continue
    return min(prices) if prices else 0.0


def _format(value: Any) -> str:
    text = str(value or "").casefold()
    if "online" in text:
        return "online"
    if "mixed" in text:
        return "hybrid"
    return "event"


def _event_from_json_ld(
    document: Mapping[str, Any],
    *,
    source_url: str,
) -> Event:
    raw = {
        "data_mode": "live",
        "id": document.get("@id"),
        "name": document.get("name"),
        "description": _plain_text(document.get("description")),
        # Preserve the exact page fetched for DAT-003 grounding. A JSON-LD
        # canonical URL may refer to another page and is therefore not used as
        # the claim citation.
        "url": source_url,
        "platform": urlparse(source_url).hostname or "Live event page",
        "date": document.get("startDate"),
        "location": _location(document.get("location")) or "Online",
        "tags": _keywords(document.get("keywords")),
        "format": _format(document.get("eventAttendanceMode")),
        "capacity": document.get(
            "maximumAttendeeCapacity",
            document.get("remainingAttendeeCapacity"),
        ),
        "price": _price(document.get("offers")),
    }
    event = normalize_event(raw)
    if event.data_mode != "live":
        raise SensoUnavailable("live event extraction lost its data-mode provenance")
    return event


def extract_events_from_page(
    body: bytes,
    *,
    source_url: str,
    content_type: str = "text/html",
) -> tuple[list[Event], str]:
    """Extract schema-valid events and plain text from one fetched page."""

    media_type = content_type.split(";", 1)[0].strip().casefold()
    if media_type and media_type not in SUPPORTED_CONTENT_TYPES:
        raise SensoUnavailable(f"unsupported event-page content type: {media_type}")
    try:
        decoded = body.decode("utf-8")
    except UnicodeDecodeError:
        decoded = body.decode("utf-8", errors="replace")

    documents: list[Any] = []
    plain_text = ""
    if media_type in {"application/json", "application/ld+json"}:
        try:
            documents.append(json.loads(decoded))
        except json.JSONDecodeError as exc:
            raise SensoUnavailable("event page returned invalid JSON") from exc
    else:
        parser = _JsonLdParser()
        parser.feed(decoded)
        plain_text = "\n".join(parser.text_parts)
        for raw_document in parser.documents:
            try:
                documents.append(json.loads(raw_document))
            except json.JSONDecodeError:
                continue

    events: list[Event] = []
    seen: set[str] = set()
    errors: list[str] = []
    for root in documents:
        for document in _iter_json_objects(root):
            if not _is_event(document):
                continue
            try:
                event = _event_from_json_ld(document, source_url=source_url)
            except (TypeError, ValueError, SensoUnavailable) as exc:
                errors.append(_safe_error(exc))
                continue
            if event.event_id not in seen:
                events.append(event)
                seen.add(event.event_id)
    if not events:
        detail = f": {errors[0]}" if errors else ""
        raise SensoUnavailable(f"no valid schema.org Event data found{detail}")
    return events, plain_text


class SensoClient:
    """Fetch live event pages and mirror their source snapshots into Senso."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout_seconds: float = 10.0,
        compile_timeout_seconds: float = 20.0,
        request: HttpRequest | None = None,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.api_key = api_key or os.getenv("SENSO_API_KEY")
        self.base_url = (
            base_url
            or os.getenv("SENSO_API_URL")
            or DEFAULT_BASE_URL
        ).rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.compile_timeout_seconds = compile_timeout_seconds
        self._request = request or _default_http_request
        self._sleep = sleeper

    @property
    def status(self) -> str:
        return "connected" if self.api_key else "demo_fallback"

    def _json_request(
        self,
        method: str,
        url: str,
        *,
        payload: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        request_headers = {
            "Accept": "application/json",
            # Match the supported request shape used by Senso's official CLI.
            "User-Agent": SENSO_CLI_USER_AGENT,
            **(dict(headers or {})),
        }
        data = None
        if payload is not None:
            request_headers["Content-Type"] = "application/json"
            data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        response = self._request(
            method,
            url,
            request_headers,
            data,
            self.timeout_seconds,
        )
        if not 200 <= response.status < 300:
            raise SensoUnavailable(f"Senso returned HTTP {response.status}")
        try:
            decoded = json.loads(response.body or b"{}")
        except json.JSONDecodeError as exc:
            raise SensoUnavailable("Senso returned invalid JSON") from exc
        if not isinstance(decoded, dict):
            raise SensoUnavailable("Senso returned an unexpected response shape")
        return decoded

    def _fetch_page(self, url: str) -> HttpResponse:
        _validate_source_url(url)
        if self._request is _default_http_request:
            _validate_resolved_host(url)
        response = self._request(
            "GET",
            url,
            {
                "Accept": "text/html,application/ld+json,application/json",
                "User-Agent": "EventCopilot/1.0 (+live event grounding)",
            },
            None,
            self.timeout_seconds,
        )
        if not 200 <= response.status < 300:
            raise SensoUnavailable(f"event source returned HTTP {response.status}")
        return response

    def _snapshot_markdown(
        self,
        *,
        source_url: str,
        plain_text: str,
        events: Sequence[Event],
    ) -> bytes:
        lines = [
            "# Live event source snapshot",
            "",
            f"Source: {source_url}",
            f"Fetched at: {_utc_now()}",
            "",
            "## Extracted events",
            "",
        ]
        for event in events:
            lines.extend(
                [
                    f"### {event.title}",
                    "",
                    event.description,
                    "",
                    f"- Starts: {event.start_time}",
                    f"- Location: {event.location}",
                    f"- Source URL: {event.source_url}",
                    "",
                ]
            )
        if plain_text.strip():
            lines.extend(["## Source text", "", plain_text.strip(), ""])
        return "\n".join(lines).encode("utf-8")

    def _ingest_snapshot(self, source_url: str, content: bytes) -> str:
        if not self.api_key:
            raise SensoUnavailable("SENSO_API_KEY is not configured")
        digest = hashlib.md5(content).hexdigest()
        filename = f"event-{hashlib.sha256(source_url.encode()).hexdigest()[:16]}.md"
        auth_headers = {"X-API-Key": self.api_key}
        upload = self._json_request(
            "POST",
            f"{self.base_url}/org/kb/upload",
            headers=auth_headers,
            payload={
                "files": [
                    {
                        "filename": filename,
                        "file_size_bytes": len(content),
                        "content_type": "text/markdown",
                        "content_hash_md5": digest,
                    }
                ]
            },
        )
        results = upload.get("results")
        if not isinstance(results, list) or not results:
            raise SensoUnavailable("Senso upload did not return a result")
        result = results[0]
        if not isinstance(result, Mapping):
            raise SensoUnavailable("Senso upload returned an invalid result")
        content_id = str(result.get("content_id") or "")
        upload_url = str(result.get("upload_url") or "")
        upload_status = str(result.get("status") or "")
        if not content_id or not upload_url:
            raise SensoUnavailable("Senso upload omitted its content ID or upload URL")
        if upload_status != "upload_pending":
            raise SensoUnavailable(
                f"Senso upload was not pending: {upload_status or 'unknown'}"
            )

        uploaded = self._request(
            "PUT",
            upload_url,
            {
                "Content-Type": "text/markdown",
                "User-Agent": SENSO_CLI_USER_AGENT,
            },
            content,
            self.timeout_seconds,
        )
        if not 200 <= uploaded.status < 300:
            raise SensoUnavailable(f"Senso object upload returned HTTP {uploaded.status}")
        self._wait_for_compile(filename, content_id, auth_headers)
        return content_id

    def _wait_for_compile(
        self,
        filename: str,
        content_id: str,
        auth_headers: Mapping[str, str],
    ) -> None:
        deadline = time.monotonic() + self.compile_timeout_seconds
        node_id = ""
        while time.monotonic() < deadline:
            found = self._json_request(
                "GET",
                f"{self.base_url}/org/kb/find?q={quote(filename)}",
                headers=auth_headers,
            )
            nodes = found.get("nodes")
            if isinstance(nodes, list):
                for node in nodes:
                    if (
                        isinstance(node, Mapping)
                        and str(node.get("content_id") or "") == content_id
                    ):
                        node_id = str(node.get("kb_node_id") or "")
                        break
            if node_id:
                status = self._json_request(
                    "GET",
                    f"{self.base_url}/org/kb/nodes/{quote(node_id)}/content",
                    headers=auth_headers,
                ).get("processing_status")
                if status in {"complete", "completed"}:
                    return
                if status in {"failed", "error"}:
                    raise SensoUnavailable("Senso compilation failed")
            self._sleep(0.5)
        raise SensoUnavailable("Senso compilation timed out")

    def crawl_events(self, urls: Sequence[str]) -> EventCrawlResult:
        """Crawl URLs now, normalize their Events, and ingest snapshots into Senso."""

        if not urls:
            raise ValueError("at least one event source URL is required")

        events: list[Event] = []
        crawled_urls: list[str] = []
        content_ids: list[str] = []
        errors: list[str] = []
        seen_event_ids: set[str] = set()

        for url in dict.fromkeys(urls):
            try:
                response = self._fetch_page(url)
                content_type = next(
                    (
                        value
                        for key, value in response.headers.items()
                        if key.casefold() == "content-type"
                    ),
                    "text/html",
                )
                page_events, plain_text = extract_events_from_page(
                    response.body,
                    source_url=url,
                    content_type=content_type,
                )
                crawled_urls.append(url)
                for event in page_events:
                    if event.event_id not in seen_event_ids:
                        events.append(event)
                        seen_event_ids.add(event.event_id)
                if self.api_key:
                    snapshot = self._snapshot_markdown(
                        source_url=url,
                        plain_text=plain_text,
                        events=page_events,
                    )
                    content_ids.append(self._ingest_snapshot(url, snapshot))
            except Exception as exc:
                errors.append(f"{url}: {_safe_error(exc, self.api_key)}")

        if not events:
            return EventCrawlResult(
                provider="Senso",
                status="crawl failed",
                mode="error",
                timestamp=_utc_now(),
                events=[],
                crawled_urls=crawled_urls,
                senso_content_ids=content_ids,
                errors=errors or ["no events were returned"],
            )

        if self.api_key and len(content_ids) == len(crawled_urls) and not errors:
            mode = "connected"
            status = "live pages crawled and compiled by Senso"
        elif self.api_key:
            mode = "error"
            status = "live crawl succeeded; one or more Senso ingestions failed"
        else:
            mode = "demo_fallback"
            status = "live pages crawled; Senso ingestion skipped because credentials are absent"

        return EventCrawlResult(
            provider="Senso",
            status=status,
            mode=mode,
            timestamp=_utc_now(),
            events=events,
            crawled_urls=crawled_urls,
            senso_content_ids=content_ids,
            errors=errors,
        )


def _write_output(result: EventCrawlResult, output_path: str | None) -> None:
    rendered = json.dumps(result.to_dict(), indent=2) + "\n"
    if output_path:
        Path(output_path).write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Crawl live event pages and ingest grounded snapshots into Senso.",
    )
    parser.add_argument("urls", nargs="+", help="event-page URLs to fetch now")
    parser.add_argument(
        "--output",
        help="optional JSON output path; stdout is used when omitted",
    )
    args = parser.parse_args(argv)
    result = SensoClient().crawl_events(args.urls)
    _write_output(result, args.output)
    return 0 if result.events else 1


if __name__ == "__main__":
    raise SystemExit(main())
