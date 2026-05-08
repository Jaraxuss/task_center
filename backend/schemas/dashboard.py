"""Dashboard, board preferences, project rename, and health response schemas."""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from ._common import normalize_project_name
from .tasks import TaskBoardGroup, TaskRead


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


class BoardPreferenceRead(BaseModel):
    task_order: list[int] = Field(default_factory=list)
    pinned_projects: list[str] = Field(default_factory=list)
    project_order: list[str] = Field(default_factory=list)


class BoardPreferenceUpdate(BaseModel):
    task_order: list[int] | None = None
    pinned_projects: list[str] | None = None
    project_order: list[str] | None = None

    @field_validator("task_order")
    @classmethod
    def normalize_task_order(cls, value: list[int] | None) -> list[int] | None:
        if value is None:
            return None
        normalized: list[int] = []
        for item in value:
            task_id = int(item)
            if task_id > 0 and task_id not in normalized:
                normalized.append(task_id)
        return normalized

    @field_validator("pinned_projects", "project_order")
    @classmethod
    def normalize_project_name_list(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        normalized: list[str] = []
        for item in value:
            project = normalize_project_name(item)
            if project and project not in normalized:
                normalized.append(project)
        return normalized


class PlanGroup(BaseModel):
    key: str
    title: str
    group_date: date | None = None
    tasks: list[TaskRead]


class PlanSummary(BaseModel):
    date: date
    total: int
    open_count: int
    plan_groups: list[PlanGroup] = Field(default_factory=list)


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
