"""Unit tests for recurrence.py.

These pin down the recurrence semantics that are most likely to regress
during refactor: monthly day-clamping, weekly multi-day, daily intervals,
end_at honouring, and timezone correctness.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from recurrence import (
    compute_next_recurrence,
    normalize_days_of_week,
    normalize_time_of_day,
    validate_recurrence_payload,
)

SH = ZoneInfo("Asia/Shanghai")
UTC = timezone.utc


def _utc(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=UTC)


def _sh(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=SH)


# --- Normalisation helpers -------------------------------------------------


class TestNormalizeTimeOfDay:
    def test_pads_hours_and_minutes(self) -> None:
        assert normalize_time_of_day("9:5") == "09:05:00"

    def test_keeps_seconds_when_present(self) -> None:
        assert normalize_time_of_day("09:05:30") == "09:05:30"

    def test_none_passthrough(self) -> None:
        assert normalize_time_of_day(None) is None

    def test_invalid_format_raises(self) -> None:
        with pytest.raises(ValueError):
            normalize_time_of_day("not-a-time")

    def test_out_of_range_raises(self) -> None:
        with pytest.raises(ValueError):
            normalize_time_of_day("25:00")


class TestNormalizeDaysOfWeek:
    def test_dedup_and_sort(self) -> None:
        assert normalize_days_of_week([3, 1, 1, 5]) == [1, 3, 5]

    def test_empty_input(self) -> None:
        assert normalize_days_of_week(None) == []
        assert normalize_days_of_week([]) == []

    def test_out_of_range_raises(self) -> None:
        with pytest.raises(ValueError):
            normalize_days_of_week([0])
        with pytest.raises(ValueError):
            normalize_days_of_week([8])


class TestValidateRecurrencePayload:
    def test_weekly_requires_days_of_week(self) -> None:
        with pytest.raises(ValueError):
            validate_recurrence_payload(
                frequency="weekly", interval=1, day_of_month=None, days_of_week=None
            )

    def test_monthly_requires_day_of_month(self) -> None:
        with pytest.raises(ValueError):
            validate_recurrence_payload(
                frequency="monthly", interval=1, day_of_month=None, days_of_week=None
            )

    def test_unknown_frequency(self) -> None:
        with pytest.raises(ValueError):
            validate_recurrence_payload(
                frequency="yearly", interval=1, day_of_month=None, days_of_week=None
            )

    def test_interval_must_be_positive(self) -> None:
        with pytest.raises(ValueError):
            validate_recurrence_payload(
                frequency="daily", interval=0, day_of_month=None, days_of_week=None
            )


# --- Daily -----------------------------------------------------------------


class TestDailyRecurrence:
    def test_at_or_after_contract_returns_anchor_when_boundary_equals_anchor(self) -> None:
        # Contract: compute_next_recurrence returns the next scheduled run
        # that is >= after_dt. When after_dt == anchor and the anchor is on
        # schedule, the anchor itself is returned. Production callers (e.g.
        # complete_task) push after_dt past the current run before calling.
        anchor = _sh(2026, 3, 19, 9, 0)
        result = compute_next_recurrence(
            frequency="daily",
            interval=1,
            anchor_at=anchor,
            after_dt=anchor,
            time_of_day="09:00",
            timezone_name="Asia/Shanghai",
        )
        assert result is not None
        assert result.astimezone(SH) == anchor

    def test_simple_next_day_after_anchor(self) -> None:
        # Boundary one second after anchor -> next run is the following day.
        anchor = _sh(2026, 3, 19, 9, 0)
        result = compute_next_recurrence(
            frequency="daily",
            interval=1,
            anchor_at=anchor,
            after_dt=anchor + timedelta(seconds=1),
            time_of_day="09:00",
            timezone_name="Asia/Shanghai",
        )
        assert result is not None
        assert result.astimezone(SH) == _sh(2026, 3, 20, 9, 0)

    def test_interval_three_days(self) -> None:
        anchor = _sh(2026, 3, 19, 9, 0)
        result = compute_next_recurrence(
            frequency="daily",
            interval=3,
            anchor_at=anchor,
            after_dt=anchor + timedelta(seconds=1),
            time_of_day="09:00",
            timezone_name="Asia/Shanghai",
        )
        assert result is not None
        assert result.astimezone(SH) == _sh(2026, 3, 22, 9, 0)

    def test_end_at_returns_none_when_passed(self) -> None:
        anchor = _sh(2026, 3, 19, 9, 0)
        result = compute_next_recurrence(
            frequency="daily",
            interval=1,
            anchor_at=anchor,
            after_dt=_sh(2026, 3, 25, 9, 0),
            time_of_day="09:00",
            end_at=_sh(2026, 3, 20, 9, 0),
            timezone_name="Asia/Shanghai",
        )
        assert result is None


# --- Weekly ----------------------------------------------------------------


class TestWeeklyRecurrence:
    def test_picks_next_listed_weekday_after_boundary(self) -> None:
        # 2026-03-19 is a Thursday (ISO weekday 4).
        # Configure: weekly on Mon (1) and Thu (4); boundary just past Thu ->
        # next match should be Mon 2026-03-23.
        anchor = _sh(2026, 3, 19, 9, 0)
        result = compute_next_recurrence(
            frequency="weekly",
            interval=1,
            anchor_at=anchor,
            after_dt=anchor + timedelta(seconds=1),
            time_of_day="09:00",
            days_of_week=[1, 4],
            timezone_name="Asia/Shanghai",
        )
        assert result is not None
        assert result.astimezone(SH) == _sh(2026, 3, 23, 9, 0)  # Monday

    def test_skips_weeks_for_interval_two(self) -> None:
        # Anchor Thu 2026-03-19; weekly every 2 weeks on Thu (4).
        # Boundary one second past anchor -> next Thu skips to week_offset=2
        # -> 2026-04-02.
        anchor = _sh(2026, 3, 19, 9, 0)
        result = compute_next_recurrence(
            frequency="weekly",
            interval=2,
            anchor_at=anchor,
            after_dt=anchor + timedelta(seconds=1),
            time_of_day="09:00",
            days_of_week=[4],
            timezone_name="Asia/Shanghai",
        )
        assert result is not None
        assert result.astimezone(SH) == _sh(2026, 4, 2, 9, 0)


# --- Monthly ---------------------------------------------------------------


class TestMonthlyRecurrence:
    def test_simple_next_month_same_day(self) -> None:
        # Anchor 2026-03-15 09:00; boundary one second past anchor ->
        # next is 2026-04-15.
        anchor = _sh(2026, 3, 15, 9, 0)
        result = compute_next_recurrence(
            frequency="monthly",
            interval=1,
            anchor_at=anchor,
            after_dt=anchor + timedelta(seconds=1),
            time_of_day="09:00",
            day_of_month=15,
            timezone_name="Asia/Shanghai",
        )
        assert result is not None
        assert result.astimezone(SH) == _sh(2026, 4, 15, 9, 0)

    def test_day_of_month_31_clamps_in_short_months(self) -> None:
        # Anchor 2026-03-31; boundary just past it -> next candidate month is
        # April which has 30 days -> 2026-04-30.
        anchor = _sh(2026, 3, 31, 9, 0)
        result = compute_next_recurrence(
            frequency="monthly",
            interval=1,
            anchor_at=anchor,
            after_dt=anchor + timedelta(seconds=1),
            time_of_day="09:00",
            day_of_month=31,
            timezone_name="Asia/Shanghai",
        )
        assert result is not None
        assert result.astimezone(SH) == _sh(2026, 4, 30, 9, 0)

    def test_day_of_month_29_in_feb_non_leap(self) -> None:
        # 2026 is not a leap year. day_of_month=29 in Feb 2026 clamps to
        # 2026-02-28.
        anchor = _sh(2026, 1, 29, 9, 0)
        result = compute_next_recurrence(
            frequency="monthly",
            interval=1,
            anchor_at=anchor,
            after_dt=anchor + timedelta(seconds=1),
            time_of_day="09:00",
            day_of_month=29,
            timezone_name="Asia/Shanghai",
        )
        assert result is not None
        assert result.astimezone(SH) == _sh(2026, 2, 28, 9, 0)

    def test_interval_three_months(self) -> None:
        anchor = _sh(2026, 1, 15, 9, 0)
        result = compute_next_recurrence(
            frequency="monthly",
            interval=3,
            anchor_at=anchor,
            after_dt=anchor + timedelta(seconds=1),
            time_of_day="09:00",
            day_of_month=15,
            timezone_name="Asia/Shanghai",
        )
        assert result is not None
        assert result.astimezone(SH) == _sh(2026, 4, 15, 9, 0)

    def test_end_at_cuts_off_future_runs(self) -> None:
        anchor = _sh(2026, 3, 15, 9, 0)
        result = compute_next_recurrence(
            frequency="monthly",
            interval=1,
            anchor_at=anchor,
            after_dt=_sh(2026, 6, 1, 9, 0),
            time_of_day="09:00",
            day_of_month=15,
            end_at=_sh(2026, 5, 1, 9, 0),
            timezone_name="Asia/Shanghai",
        )
        assert result is None


# --- Time-of-day inheritance ----------------------------------------------


class TestTimeOfDayInheritance:
    def test_uses_anchor_time_when_time_of_day_omitted(self) -> None:
        anchor = _sh(2026, 3, 19, 14, 30)
        result = compute_next_recurrence(
            frequency="daily",
            interval=1,
            anchor_at=anchor,
            after_dt=anchor + timedelta(seconds=1),
            timezone_name="Asia/Shanghai",
        )
        assert result is not None
        assert result.astimezone(SH) == _sh(2026, 3, 20, 14, 30)


# --- Timezone correctness --------------------------------------------------


class TestTimezone:
    def test_returns_utc_aware_datetime(self) -> None:
        anchor = _sh(2026, 3, 19, 9, 0)
        result = compute_next_recurrence(
            frequency="daily",
            interval=1,
            anchor_at=anchor,
            after_dt=anchor + timedelta(seconds=1),
            time_of_day="09:00",
            timezone_name="Asia/Shanghai",
        )
        assert result is not None
        assert result.tzinfo == UTC
        # 09:00 SH on the next day == 01:00 UTC.
        assert result.hour == 1

    def test_default_timezone_is_app_timezone(self) -> None:
        # Without explicit timezone_name, APP_TIMEZONE (Asia/Shanghai) is used.
        anchor = _sh(2026, 3, 19, 9, 0)
        result = compute_next_recurrence(
            frequency="daily",
            interval=1,
            anchor_at=anchor,
            after_dt=anchor + timedelta(seconds=1),
            time_of_day="09:00",
        )
        assert result is not None
        assert result.astimezone(SH) == _sh(2026, 3, 20, 9, 0)
