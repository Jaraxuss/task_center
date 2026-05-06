from __future__ import annotations

from calendar import monthrange
from datetime import datetime, time, timedelta, tzinfo
from zoneinfo import ZoneInfo

from timeutils import APP_TIMEZONE, UTC, ensure_aware_datetime

VALID_FREQUENCIES = {"daily", "weekly", "monthly"}


def parse_time_of_day(value: str | None) -> time | None:
    if value is None:
        return None
    parts = value.strip().split(":")
    if len(parts) not in {2, 3}:
        raise ValueError("time_of_day must be HH:MM or HH:MM:SS")
    hour = int(parts[0])
    minute = int(parts[1])
    second = int(parts[2]) if len(parts) == 3 else 0
    if hour < 0 or hour > 23 or minute < 0 or minute > 59 or second < 0 or second > 59:
        raise ValueError("time_of_day is out of range")
    return time(hour=hour, minute=minute, second=second)



def normalize_time_of_day(value: str | None) -> str | None:
    parsed = parse_time_of_day(value)
    if parsed is None:
        return None
    return parsed.strftime("%H:%M:%S")



def normalize_days_of_week(values: list[int] | None) -> list[int]:
    if not values:
        return []
    normalized = sorted({int(value) for value in values})
    for value in normalized:
        if value < 1 or value > 7:
            raise ValueError("days_of_week values must be between 1 and 7")
    return normalized



def validate_recurrence_payload(
    *,
    frequency: str,
    interval: int,
    day_of_month: int | None,
    days_of_week: list[int] | None,
) -> None:
    if frequency not in VALID_FREQUENCIES:
        raise ValueError(f"frequency must be one of {sorted(VALID_FREQUENCIES)}")
    if interval < 1:
        raise ValueError("interval must be >= 1")
    normalized_days = normalize_days_of_week(days_of_week)
    if frequency == "weekly" and not normalized_days:
        raise ValueError("weekly recurrence requires days_of_week")
    if frequency == "monthly" and day_of_month is None:
        raise ValueError("monthly recurrence requires day_of_month")
    if day_of_month is not None and (day_of_month < 1 or day_of_month > 31):
        raise ValueError("day_of_month must be between 1 and 31")



def add_months(year: int, month: int, months: int) -> tuple[int, int]:
    total = (year * 12 + (month - 1)) + months
    return total // 12, total % 12 + 1



def candidate_monthly_datetime(year: int, month: int, day_of_month: int, candidate_time: time, tz: tzinfo) -> datetime:
    max_day = monthrange(year, month)[1]
    day = min(day_of_month, max_day)
    return datetime(year, month, day, candidate_time.hour, candidate_time.minute, candidate_time.second, tzinfo=tz)



def compute_next_recurrence(
    *,
    frequency: str,
    interval: int = 1,
    anchor_at: datetime,
    after_dt: datetime | None = None,
    time_of_day: str | None = None,
    days_of_week: list[int] | None = None,
    day_of_month: int | None = None,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    timezone_name: str | None = None,
) -> datetime | None:
    validate_recurrence_payload(
        frequency=frequency,
        interval=interval,
        day_of_month=day_of_month,
        days_of_week=days_of_week,
    )

    tz = ZoneInfo(timezone_name) if timezone_name else APP_TIMEZONE
    effective_anchor_utc = ensure_aware_datetime(start_at or anchor_at, assume_tz=tz)
    boundary_utc = ensure_aware_datetime(after_dt or effective_anchor_utc, assume_tz=tz)
    end_at_utc = ensure_aware_datetime(end_at, assume_tz=tz)
    if effective_anchor_utc is None or boundary_utc is None:
        raise ValueError("anchor_at is required")

    effective_anchor = effective_anchor_utc.astimezone(tz)
    boundary = max(boundary_utc.astimezone(tz), effective_anchor)
    end_boundary = end_at_utc.astimezone(tz) if end_at_utc else None
    candidate_time = parse_time_of_day(time_of_day) or effective_anchor.time().replace(microsecond=0)
    normalized_days = normalize_days_of_week(days_of_week)

    if frequency == "daily":
        current = datetime.combine(effective_anchor.date(), candidate_time, tzinfo=tz)
        while current < boundary:
            current += timedelta(days=interval)
        if end_boundary and current > end_boundary:
            return None
        return current.astimezone(UTC)

    if frequency == "weekly":
        week_start = effective_anchor.date() - timedelta(days=effective_anchor.isoweekday() - 1)
        week_offset = 0
        while True:
            current_week_start = week_start + timedelta(weeks=week_offset)
            for weekday in normalized_days:
                current = datetime.combine(current_week_start + timedelta(days=weekday - 1), candidate_time, tzinfo=tz)
                if current < effective_anchor:
                    continue
                if current < boundary:
                    continue
                if end_boundary and current > end_boundary:
                    return None
                return current.astimezone(UTC)
            week_offset += interval

    # validate_recurrence_payload above guarantees day_of_month is set when
    # frequency == "monthly"; assert for the type checker.
    assert day_of_month is not None
    months_added = 0
    while True:
        year, month = add_months(effective_anchor.year, effective_anchor.month, months_added)
        current = candidate_monthly_datetime(year, month, day_of_month, candidate_time, tz)
        if current >= effective_anchor and current >= boundary:
            if end_boundary and current > end_boundary:
                return None
            return current.astimezone(UTC)
        months_added += interval
