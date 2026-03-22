from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from models import EventType, ReminderStatus, TaskStatus


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


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    due_at: datetime | None = None
    project: str | None = Field(default=None, max_length=128)
    tags: list[str] | None = None
    source: str | None = None
    status: str | None = None

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


class TodaySummary(BaseModel):
    date: date
    tasks: list[TaskRead]
    total: int
    open_count: int
    completed_count: int


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
