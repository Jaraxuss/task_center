"""Shared helper functions and Literal type aliases used across schema modules."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from timeutils import APP_TIMEZONE, to_utc_datetime


def normalize_datetime_input(value: datetime | str | None) -> datetime | None:
    return to_utc_datetime(value, assume_tz=APP_TIMEZONE)


def normalize_project_name(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def normalize_string_list(value: list[str] | None) -> list[str]:
    normalized: list[str] = []
    if not value:
        return normalized
    for item in value:
        text = str(item).strip()
        if text and text not in normalized:
            normalized.append(text)
    return normalized


def normalize_required_text(value: str | None, *, field_name: str) -> str:
    normalized = (value or "").strip()
    if not normalized:
        raise ValueError(f"{field_name} cannot be empty")
    return normalized


# ── Literal type aliases ────────────────────────────────────────────
CustomerMaterialStatusValue = Literal["pending", "approved", "skipped", "uploaded"]
CustomerStatusValue = Literal["active", "paused", "closed"]
ProjectStatusValue = Literal["active", "waiting", "done", "canceled"]
ProjectTypeValue = Literal["customer", "personal", "internal"]
FactStatusValue = Literal["draft", "confirmed", "rejected"]
FactSourceTypeValue = Literal[
    "chat", "screenshot_ocr", "task_completion",
    "meeting_note", "manual_input", "forwarded_message", "document",
]
MaterialTypeValue = Literal["period_summary", "fact_bundle", "meeting_note", "project_digest"]
ReviewBatchStatusValue = Literal["pending", "partial", "approved", "uploaded"]
ReviewBatchTypeValue = Literal["weekly_customer_summary", "daily_customer_summary", "manual_generation"]
