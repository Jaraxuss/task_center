from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from models import ReminderStatus, TaskStatus
from recurrence import normalize_days_of_week, normalize_time_of_day, validate_recurrence_payload


class ReminderCreate(BaseModel):
    remind_at: datetime
    channel: str = "local"
    note: str | None = None


class ReminderRead(BaseModel):
    id: int
    task_id: int
    remind_at: datetime
    channel: str
    status: str
    note: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TaskRecurrenceBase(BaseModel):
    enabled: bool = True
    frequency: Literal["daily", "weekly", "monthly"]
    interval: int = Field(default=1, ge=1, le=365)
    timezone: str = Field(default="UTC", min_length=1, max_length=64)
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



def normalize_project_name(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


class TaskBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    due_at: datetime | None = None
    project: str | None = Field(default=None, max_length=128)
    tags: list[str] = Field(default_factory=list)
    source: str = "web"

    @field_validator("project", mode="before")
    @classmethod
    def normalize_project(cls, value: str | None) -> str | None:
        return normalize_project_name(value)


class TaskCreate(TaskBase):
    reminders: list[ReminderCreate] = Field(default_factory=list)
    recurrence: TaskRecurrenceWrite | None = None


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    due_at: datetime | None = None
    project: str | None = Field(default=None, max_length=128)
    tags: list[str] | None = None
    source: str | None = None
    status: str | None = None
    recurrence: TaskRecurrenceWrite | None = None
    clear_recurrence: bool = False

    @field_validator("project", mode="before")
    @classmethod
    def normalize_project(cls, value: str | None) -> str | None:
        return normalize_project_name(value)


class TaskActionComplete(BaseModel):
    completed_at: datetime | None = None


class TaskActionCancel(BaseModel):
    canceled_at: datetime | None = None
    reason: str | None = None


class TaskActionDefer(BaseModel):
    deferred_to: datetime
    due_at: datetime | None = None
    reason: str | None = None


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
    tags: list[str]
    source: str
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
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


class ProjectSummary(BaseModel):
    name: str
    task_count: int
    open_task_count: int
    done_task_count: int


class ProjectRenameRequest(BaseModel):
    old_name: str = Field(..., min_length=1, max_length=128)
    new_name: str = Field(..., min_length=1, max_length=128)

    @field_validator("old_name", "new_name", mode="before")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = normalize_project_name(value)
        if not normalized:
            raise ValueError("Project name cannot be empty")
        return normalized


class ProjectRenameResponse(BaseModel):
    old_name: str
    new_name: str
    updated_task_count: int
    project: ProjectSummary


class PlanGroup(BaseModel):
    key: str
    title: str
    group_date: date | None = None
    tasks: list[TaskRead]


class TodaySummary(BaseModel):
    date: date
    tasks: list[TaskRead]
    total: int
    open_count: int
    completed_count: int
    plan_groups: list[PlanGroup] = Field(default_factory=list)


class BoardSummary(BaseModel):
    groups: list[TaskBoardGroup]


class HistorySummary(BaseModel):
    tasks: list[TaskRead]
    total: int


class DashboardPayload(BaseModel):
    today: TodaySummary
    board: BoardSummary
    history: HistorySummary


class HealthResponse(BaseModel):
    status: Literal["ok"]
    db: str
    now: datetime


class NightlyReviewPlaceholder(BaseModel):
    cutoff_hour: int = 22
    supported: bool = True
    note: str
    pending_candidates: int
