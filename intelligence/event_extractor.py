"""Normalize raw event records into the shared Event contract."""

from __future__ import annotations

import hashlib
from typing import Any

from shared.contracts import SCHEMA_VERSION, Event

from .pioneer_client import PioneerClient, PioneerUnavailable


def _fraction(value: Any, default: float) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return default
    if numeric > 1:
        numeric /= 100
    return max(0.0, min(1.0, numeric))


def normalize_event(raw: dict[str, Any]) -> Event:
    """Map common event-page fields into the stable Event schema."""

    title = str(raw.get("title") or raw.get("name") or "Untitled event")
    event_id = str(raw.get("event_id") or raw.get("id") or "")
    if not event_id:
        identity = f"{title}|{raw.get('start_time', raw.get('date', ''))}"
        event_id = f"evt_{hashlib.sha1(identity.encode()).hexdigest()[:10]}"

    themes = raw.get("themes") or raw.get("topics") or raw.get("tags") or []
    if isinstance(themes, str):
        themes = [item.strip() for item in themes.split(",") if item.strip()]
    if not themes:
        themes = ["general"]

    raw_crowd_size = raw.get("estimated_crowd_size", raw.get("capacity"))
    crowd_size = (
        None
        if raw_crowd_size in (None, "")
        else max(0, int(raw_crowd_size))
    )

    return Event(
        schema_version=str(raw.get("schema_version") or SCHEMA_VERSION),
        data_mode=str(raw.get("data_mode") or "fixture"),
        event_id=event_id,
        title=title,
        description=str(
            raw.get("description")
            or raw.get("summary")
            or "No source description was provided."
        ),
        source_url=str(raw.get("source_url") or raw.get("url") or ""),
        source_name=str(raw.get("source_name") or raw.get("platform") or "Unknown"),
        start_time=str(raw.get("start_time") or raw.get("date") or ""),
        location=str(raw.get("location") or raw.get("venue") or "Unknown"),
        themes=[str(theme) for theme in themes],
        format=str(raw.get("format") or raw.get("event_type") or "event").lower(),
        interaction_level=_fraction(raw.get("interaction_level"), 0.5),
        knowledge_depth=_fraction(raw.get("knowledge_depth"), 0.5),
        estimated_crowd_size=crowd_size,
        cost_usd=max(0.0, float(raw.get("cost_usd") or raw.get("price") or 0)),
    )


def extract_event(raw: dict[str, Any], pioneer: PioneerClient | None = None) -> tuple[Event, str]:
    """Use Pioneer when configured and always fall back to deterministic normalization."""

    if pioneer is not None:
        try:
            extracted, status = pioneer.extract(raw)
            extracted = dict(extracted)
            extracted["data_mode"] = (
                "live" if status == "connected" else "fixture"
            )
            return normalize_event(extracted), status
        except PioneerUnavailable:
            pass
    return normalize_event(raw), "local normalization"
