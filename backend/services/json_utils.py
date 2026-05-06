"""JSON helpers used across services and routers.

These tolerant parsers exist because the legacy schema stores arrays/objects
as TEXT JSON columns. They never raise on malformed input; instead they
fall back to empty values so callers can rely on a stable shape.
"""

from __future__ import annotations

import json
from typing import Any


def parse_json_object(raw_value: str | None) -> dict[str, Any]:
    if not raw_value:
        return {}
    try:
        value = json.loads(raw_value)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def parse_json_list(raw_value: str | None) -> list[str]:
    if not raw_value:
        return []
    try:
        value = json.loads(raw_value)
    except json.JSONDecodeError:
        return []
    if not isinstance(value, list):
        return []
    normalized: list[str] = []
    for item in value:
        text = str(item).strip()
        if text and text not in normalized:
            normalized.append(text)
    return normalized


__all__ = ["parse_json_object", "parse_json_list"]
