"""Unit tests for timeutils.

These are pure-logic tests that do not touch the database.
"""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from timeutils import (
    APP_TIMEZONE,
    UTC,
    ensure_aware_datetime,
    local_date,
    local_day_bounds,
    parse_datetime_string,
    to_storage_string,
    to_utc_datetime,
)


class TestParseDatetimeString:
    def test_parses_z_suffix_as_utc(self) -> None:
        result = parse_datetime_string("2026-03-19T15:00:00Z")
        assert result == datetime(2026, 3, 19, 15, 0, 0, tzinfo=timezone.utc)

    def test_parses_offset_suffix(self) -> None:
        result = parse_datetime_string("2026-03-19T23:00:00+08:00")
        assert result.utcoffset().total_seconds() == 8 * 3600

    def test_parses_naive_string(self) -> None:
        result = parse_datetime_string("2026-03-19T15:00:00")
        # parse_datetime_string doesn't attach a tz when none is present.
        assert result.tzinfo is None


class TestEnsureAwareDatetime:
    def test_none_returns_none(self) -> None:
        assert ensure_aware_datetime(None) is None

    def test_naive_string_assumes_app_timezone(self) -> None:
        result = ensure_aware_datetime("2026-03-19T15:00:00")
        assert result is not None
        assert result.tzinfo is not None
        # 15:00 Asia/Shanghai == 07:00 UTC
        assert result.astimezone(UTC).hour == 7

    def test_naive_datetime_assumes_app_timezone(self) -> None:
        naive = datetime(2026, 3, 19, 15, 0, 0)
        result = ensure_aware_datetime(naive)
        assert result is not None
        assert result.tzinfo is not None

    def test_aware_datetime_passthrough(self) -> None:
        aware = datetime(2026, 3, 19, 15, 0, 0, tzinfo=timezone.utc)
        result = ensure_aware_datetime(aware)
        assert result is aware


class TestToUtcDatetime:
    def test_shanghai_to_utc(self) -> None:
        # 23:00 +08:00 == 15:00 UTC
        result = to_utc_datetime("2026-03-19T23:00:00+08:00")
        assert result == datetime(2026, 3, 19, 15, 0, 0, tzinfo=timezone.utc)

    def test_naive_uses_assume_tz(self) -> None:
        # Naive 23:00 assumed to be Shanghai == 15:00 UTC.
        result = to_utc_datetime("2026-03-19T23:00:00")
        assert result == datetime(2026, 3, 19, 15, 0, 0, tzinfo=timezone.utc)


class TestToStorageString:
    def test_utc_normalized_to_z_suffix(self) -> None:
        dt = datetime(2026, 3, 19, 15, 0, 0, tzinfo=timezone.utc)
        assert to_storage_string(dt) == "2026-03-19T15:00:00Z"

    def test_offset_input_converted_to_utc(self) -> None:
        # 23:00 +08:00 -> 15:00Z
        assert to_storage_string("2026-03-19T23:00:00+08:00") == "2026-03-19T15:00:00Z"

    def test_none_returns_none(self) -> None:
        assert to_storage_string(None) is None


class TestLocalDayBounds:
    def test_returns_utc_bounds_for_local_day(self) -> None:
        # 2026-03-19 in Asia/Shanghai -> [2026-03-18T16:00Z, 2026-03-19T16:00Z)
        from datetime import date as date_cls

        start, end = local_day_bounds(date_cls(2026, 3, 19))
        assert start.tzinfo == timezone.utc
        assert end.tzinfo == timezone.utc
        assert start == datetime(2026, 3, 18, 16, 0, tzinfo=timezone.utc)
        assert end == datetime(2026, 3, 19, 16, 0, tzinfo=timezone.utc)


class TestLocalDate:
    def test_z_suffix_converted_to_local_date(self) -> None:
        # 2026-03-18T16:00Z is 2026-03-19 00:00 in Asia/Shanghai.
        assert str(local_date("2026-03-18T16:00:00Z")) == "2026-03-19"

    def test_naive_string_assumed_local(self) -> None:
        # Naive 23:00 is treated as Shanghai by default; same calendar day.
        assert str(local_date("2026-03-19T23:00:00")) == "2026-03-19"

    def test_none_returns_none(self) -> None:
        assert local_date(None) is None


def test_app_timezone_is_shanghai() -> None:
    assert APP_TIMEZONE == ZoneInfo("Asia/Shanghai")
