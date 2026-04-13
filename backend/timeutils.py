from __future__ import annotations

from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

APP_TIMEZONE = ZoneInfo("Asia/Shanghai")
UTC = timezone.utc


def parse_datetime_string(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    return datetime.fromisoformat(text)


def ensure_aware_datetime(value: datetime | str | None, *, assume_tz=APP_TIMEZONE) -> datetime | None:
    if value is None:
        return None
    dt = parse_datetime_string(value) if isinstance(value, str) else value
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=assume_tz)
    return dt


def to_utc_datetime(value: datetime | str | None, *, assume_tz=APP_TIMEZONE) -> datetime | None:
    dt = ensure_aware_datetime(value, assume_tz=assume_tz)
    if dt is None:
        return None
    return dt.astimezone(UTC)


def to_storage_string(value: datetime | str | None, *, assume_tz=APP_TIMEZONE) -> str | None:
    dt = to_utc_datetime(value, assume_tz=assume_tz)
    if dt is None:
        return None
    return dt.isoformat().replace("+00:00", "Z")


def now_utc() -> datetime:
    return datetime.now(UTC)


def now_local() -> datetime:
    return now_utc().astimezone(APP_TIMEZONE)


def today_local() -> date:
    return now_local().date()


def local_day_bounds(target: date, *, tz=APP_TIMEZONE) -> tuple[datetime, datetime]:
    from datetime import timedelta

    start_local = datetime.combine(target, time.min, tzinfo=tz)
    end_local = start_local + timedelta(days=1)
    return start_local.astimezone(UTC), end_local.astimezone(UTC)


def local_date(value: datetime | str | None, *, tz=APP_TIMEZONE) -> date | None:
    dt = ensure_aware_datetime(value, assume_tz=tz)
    if dt is None:
        return None
    return dt.astimezone(tz).date()
