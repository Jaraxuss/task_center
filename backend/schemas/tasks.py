"""Pydantic schemas for tasks, reminders, and recurrence rules."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from recurrence import normalize_days_of_week, normalize_time_of_day, validate_recurrence_payload

from ._common import normalize_datetime_input, normalize_project_name


class ReminderCreate(BaseModel):
    remind_at: datetime
    channel: str = "local"
    note: str | None = None
    delivery_mode: Literal["feishu_card_v2", "feishu_card_v1", "openclaw_cron_agent"] | None = None
    receive_id: str | None = Field(default=None, max_length=128)
    receive_id_type: Literal["open_id", "user_id", "union_id", "email", "chat_id"] | None = None
    ai_prompt: str | None = None

    @field_validator("remind_at", mode="before")
    @classmethod
    def normalize_remind_at(cls, value: datetime | str | None) -> datetime | None:
        return normalize_datetime_input(value)

    @field_validator("note", "receive_id", "ai_prompt", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @model_validator(mode="after")
    def validate_ai_prompt(self) -> "ReminderCreate":
        if self.delivery_mode == "openclaw_cron_agent" and not self.ai_prompt:
            raise ValueError("ai_prompt is required when delivery_mode is openclaw_cron_agent")
        return self


class ReminderRead(BaseModel):
    id: int
    task_id: int
    remind_at: datetime
    channel: str
    status: str
    note: str | None
    delivery_mode: str | None = None
    receive_id: str | None = None
    receive_id_type: str | None = None
    external_cron_job_id: str | None = None
    message_id: str | None = None
    request_uuid: str | None = None
    fired_at: datetime | None = None
    last_error: str | None = None
    retry_count: int = 0
    ai_prompt: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ReminderUpdate(BaseModel):
    remind_at: datetime | None = None
    channel: str | None = None
    note: str | None = None
    delivery_mode: Literal["feishu_card_v2", "feishu_card_v1", "openclaw_cron_agent"] | None = None
    receive_id: str | None = Field(default=None, max_length=128)
    receive_id_type: Literal["open_id", "user_id", "union_id", "email", "chat_id"] | None = None
    ai_prompt: str | None = None

    @field_validator("remind_at", mode="before")
    @classmethod
    def normalize_remind_at(cls, value: datetime | str | None) -> datetime | None:
        return normalize_datetime_input(value)

    @field_validator("note", "receive_id", "ai_prompt", "channel", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class TaskRecurrenceBase(BaseModel):
    enabled: bool = True
    frequency: Literal["daily", "weekly", "monthly"]
    interval: int = Field(default=1, ge=1, le=365)
    timezone: str = Field(default="Asia/Shanghai", min_length=1, max_length=64)
    time_of_day: str | None = Field(default=None, description="HH:MM or HH:MM:SS")
    days_of_week: list[int] = Field(default_factory=list, description="ISO weekday numbers: 1=Mon ... 7=Sun")
    day_of_month: int | None = Field(default=None, ge=1, le=31)
    start_at: datetime | None = None
    end_at: datetime | None = None
    reminder_offsets_minutes: list[int] = Field(default_factory=list, description="Minutes before due time, e.g. [30, 1440]")

    @field_validator("time_of_day", mode="before")
    @classmethod
    def normalize_time(cls, value: str | None) -> str | None:
        return normalize_time_of_day(value)

    @field_validator("days_of_week", mode="before")
    @classmethod
    def normalize_weekdays(cls, value: list[int] | None) -> list[int]:
        return normalize_days_of_week(value)

    @field_validator("reminder_offsets_minutes")
    @classmethod
    def normalize_offsets(cls, value: list[int]) -> list[int]:
        normalized = sorted({int(item) for item in value})
        for item in normalized:
            if item < 0:
                raise ValueError("reminder_offsets_minutes must be >= 0")
        return normalized

    @field_validator("start_at", "end_at", mode="before")
    @classmethod
    def normalize_recurrence_datetimes(cls, value: datetime | str | None) -> datetime | None:
        return normalize_datetime_input(value)

    @model_validator(mode="after")
    def validate_rule(self) -> "TaskRecurrenceBase":
        validate_recurrence_payload(
            frequency=self.frequency,
            interval=self.interval,
            day_of_month=self.day_of_month,
            days_of_week=self.days_of_week,
        )
        if self.end_at and self.start_at and self.end_at < self.start_at:
            raise ValueError("end_at must be later than start_at")
        return self


class TaskRecurrenceWrite(TaskRecurrenceBase):
    pass


class TaskRecurrenceRead(TaskRecurrenceBase):
    id: int
    task_id: int
    next_run_at: datetime | None
    last_run_at: datetime | None
    created_at: datetime
    updated_at: datetime


class TaskBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    due_at: datetime | None = None
    project: str | None = Field(default=None, max_length=128)
    area: str | None = Field(default=None, max_length=128)
    customer_id: int | None = None
    project_id: int | None = None
    tags: list[str] = Field(default_factory=list)
    source: str = "web"
    source_type: str | None = Field(default=None, max_length=32)

    @field_validator("project", mode="before")
    @classmethod
    def normalize_project(cls, value: str | None) -> str | None:
        return normalize_project_name(value)

    @field_validator("due_at", mode="before")
    @classmethod
    def normalize_due_at(cls, value: datetime | str | None) -> datetime | None:
        return normalize_datetime_input(value)


class TaskCreate(TaskBase):
    reminders: list[ReminderCreate] = Field(default_factory=list)
    recurrence: TaskRecurrenceWrite | None = None


class TaskUpdateCompat(BaseModel):
    """Old TaskUpdate – kept for reference. The actual TaskUpdate now includes v2 fields."""
    pass


class TaskActionComplete(BaseModel):
    completed_at: datetime | None = None
    note: str | None = None

    @field_validator("completed_at", mode="before")
    @classmethod
    def normalize_completed_at(cls, value: datetime | str | None) -> datetime | None:
        return normalize_datetime_input(value)

    @field_validator("note", mode="before")
    @classmethod
    def normalize_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class TaskActionCancel(BaseModel):
    canceled_at: datetime | None = None
    reason: str | None = None

    @field_validator("canceled_at", mode="before")
    @classmethod
    def normalize_canceled_at(cls, value: datetime | str | None) -> datetime | None:
        return normalize_datetime_input(value)


class TaskActionDefer(BaseModel):
    deferred_to: datetime
    due_at: datetime | None = None
    reason: str | None = None

    @field_validator("deferred_to", "due_at", mode="before")
    @classmethod
    def normalize_defer_datetimes(cls, value: datetime | str | None) -> datetime | None:
        return normalize_datetime_input(value)


class TaskEventRead(BaseModel):
    id: int
    task_id: int
    event_type: str
    payload: dict
    created_at: datetime


class TaskRead(BaseModel):
    id: int
    title: str
    description: str | None
    due_at: datetime | None
    status: str
    project: str | None
    area: str | None
    customer_id: int | None
    project_id: int | None
    tags: list[str]
    source: str
    source_type: str | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
    completion_note: str | None
    canceled_at: datetime | None
    deferred_to: datetime | None
    nightly_bucket: str | None
    nightly_reviewed_at: datetime | None
    reminders: list[ReminderRead] = Field(default_factory=list)
    recurrence: TaskRecurrenceRead | None = None


class TaskDetail(TaskRead):
    events: list[TaskEventRead] = Field(default_factory=list)


class TaskBoardGroup(BaseModel):
    status: str
    tasks: list[TaskRead]


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    due_at: datetime | None = None
    project: str | None = Field(default=None, max_length=128)
    area: str | None = Field(default=None, max_length=128)
    customer_id: int | None = None
    project_id: int | None = None
    tags: list[str] | None = None
    source: str | None = None
    source_type: str | None = Field(default=None, max_length=32)
    status: str | None = None
    recurrence: TaskRecurrenceWrite | None = None
    clear_recurrence: bool = False
    clear_customer: bool = False
    clear_project_v2: bool = False

    @field_validator("project", mode="before")
    @classmethod
    def normalize_project(cls, value: str | None) -> str | None:
        return normalize_project_name(value)

    @field_validator("due_at", mode="before")
    @classmethod
    def normalize_due_at(cls, value: datetime | str | None) -> datetime | None:
        return normalize_datetime_input(value)

    @field_validator("area", mode="before")
    @classmethod
    def normalize_area(cls, value: str | None) -> str | None:
        return normalize_project_name(value)
