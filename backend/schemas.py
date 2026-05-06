from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from recurrence import normalize_days_of_week, normalize_time_of_day, validate_recurrence_payload
from timeutils import APP_TIMEZONE, to_utc_datetime


def normalize_datetime_input(value: datetime | str | None) -> datetime | None:
    return to_utc_datetime(value, assume_tz=APP_TIMEZONE)


class ReminderCreate(BaseModel):
    remind_at: datetime
    channel: str = "local"
    note: str | None = None

    @field_validator("remind_at", mode="before")
    @classmethod
    def normalize_remind_at(cls, value: datetime | str | None) -> datetime | None:
        return normalize_datetime_input(value)


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



def normalize_project_name(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


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


class CustomerMaterialBase(BaseModel):
    project: str | None = Field(default=None, max_length=128)
    title: str = Field(..., min_length=1, max_length=255)
    material_date: datetime | None = None
    source_type: str = Field(default="text", max_length=32)
    source: str = Field(default="chat", max_length=32)
    source_refs: dict[str, Any] = Field(default_factory=dict)
    value_types: list[str] = Field(default_factory=list)
    status: CustomerMaterialStatusValue = "pending"
    task_id: int | None = None
    # V2 fields (consolidated into main schema per API consolidation plan)
    customer_id: int | None = None
    project_v2_id: int | None = None
    review_batch_id: int | None = None
    material_type: MaterialTypeValue = "period_summary"
    period_start: datetime | None = None
    period_end: datetime | None = None
    raw_facts_markdown: str | None = None
    generation_meta: dict[str, Any] | None = None

    @field_validator("project", mode="before")
    @classmethod
    def normalize_material_project(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = normalize_project_name(value)
        if not normalized:
            raise ValueError("project cannot be empty")
        return normalized

    @field_validator("title", mode="before")
    @classmethod
    def normalize_title(cls, value: str | None) -> str:
        return normalize_required_text(value, field_name="title")

    @field_validator("source_type", mode="before")
    @classmethod
    def normalize_source_type(cls, value: str | None) -> str:
        return (value or "").strip() or "text"

    @field_validator("source", mode="before")
    @classmethod
    def normalize_source(cls, value: str | None) -> str:
        return (value or "").strip() or "chat"

    @field_validator("material_date", mode="before")
    @classmethod
    def normalize_material_date(cls, value: datetime | str | None) -> datetime | None:
        return normalize_datetime_input(value)

    @field_validator("value_types", mode="before")
    @classmethod
    def normalize_value_types(cls, value: list[str] | None) -> list[str]:
        return normalize_string_list(value)

    @field_validator("period_start", "period_end", mode="before")
    @classmethod
    def normalize_period_dt(cls, value: datetime | str | None) -> datetime | None:
        return normalize_datetime_input(value)

    @model_validator(mode="after")
    def require_legacy_project_or_customer(self) -> "CustomerMaterialBase":
        if self.project is None and self.customer_id is None:
            raise ValueError("project or customer_id is required")
        return self


class CustomerMaterialCreate(CustomerMaterialBase):
    pass


class CustomerMaterialUpdate(BaseModel):
    project: str | None = Field(default=None, max_length=128)
    title: str | None = Field(default=None, min_length=1, max_length=255)
    material_date: datetime | None = None
    source_type: str | None = Field(default=None, max_length=32)
    source: str | None = Field(default=None, max_length=32)
    source_refs: dict[str, Any] | None = None
    value_types: list[str] | None = None
    status: CustomerMaterialStatusValue | None = None
    task_id: int | None = None
    clear_task: bool = False
    # V2 fields
    customer_id: int | None = None
    project_v2_id: int | None = None
    review_batch_id: int | None = None
    material_type: MaterialTypeValue | None = None
    period_start: datetime | None = None
    period_end: datetime | None = None
    raw_facts_markdown: str | None = None
    generation_meta: dict[str, Any] | None = None
    clear_project_v2: bool = False
    clear_batch: bool = False

    @field_validator("project", mode="before")
    @classmethod
    def normalize_material_project(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = normalize_project_name(value)
        if not normalized:
            raise ValueError("project cannot be empty")
        return normalized

    @field_validator("title", mode="before")
    @classmethod
    def normalize_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return normalize_required_text(value, field_name="title")

    @field_validator("source_type", "source", mode="before")
    @classmethod
    def normalize_optional_short_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None

    @field_validator("material_date", mode="before")
    @classmethod
    def normalize_material_date(cls, value: datetime | str | None) -> datetime | None:
        return normalize_datetime_input(value)

    @field_validator("value_types", mode="before")
    @classmethod
    def normalize_value_types(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        return normalize_string_list(value)


class CustomerMaterialRead(BaseModel):
    id: int
    project: str | None
    title: str
    material_date: datetime | None
    source_type: str
    source: str
    source_refs: dict[str, Any]
    value_types: list[str]
    status: str
    task_id: int | None
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None
    # V2 fields
    customer_id: int | None = None
    project_v2_id: int | None = None
    review_batch_id: int | None = None
    material_type: str | None = None
    period_start: datetime | None = None
    period_end: datetime | None = None
    raw_facts_markdown: str | None = None
    generation_meta: dict[str, Any] | None = None


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


# ────────────────────────────────────────────────────────────────────
# V2 schemas: Customers, Projects (new model), Facts, ReviewBatches,
# CustomerMaterialFacts
# ────────────────────────────────────────────────────────────────────


class CustomerCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    key: str | None = Field(default=None, max_length=64)
    aliases: list[str] = Field(default_factory=list)
    status: CustomerStatusValue = "active"
    description: str | None = None
    area: str | None = Field(default=None, max_length=128)
    tags: list[str] = Field(default_factory=list)

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, v: str | None) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("name cannot be empty")
        return v

    @field_validator("key", mode="before")
    @classmethod
    def normalize_key(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        return v or None

    @field_validator("area", mode="before")
    @classmethod
    def normalize_area(cls, v: str | None) -> str | None:
        return normalize_project_name(v)

    @field_validator("aliases", "tags", mode="before")
    @classmethod
    def normalize_str_list(cls, v: list[str] | None) -> list[str]:
        return normalize_string_list(v)


class CustomerUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    key: str | None = Field(default=None, max_length=64)
    aliases: list[str] | None = None
    status: CustomerStatusValue | None = None
    description: str | None = None
    area: str | None = Field(default=None, max_length=128)
    tags: list[str] | None = None

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        if not v:
            raise ValueError("name cannot be empty")
        return v

    @field_validator("key", mode="before")
    @classmethod
    def normalize_key(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        return v or None

    @field_validator("area", mode="before")
    @classmethod
    def normalize_area(cls, v: str | None) -> str | None:
        return normalize_project_name(v)

    @field_validator("aliases", "tags", mode="before")
    @classmethod
    def normalize_str_list(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        return normalize_string_list(v)


class CustomerRead(BaseModel):
    id: int
    name: str
    key: str | None
    aliases: list[str]
    status: str
    description: str | None
    area: str | None
    tags: list[str]
    created_at: datetime
    updated_at: datetime


class ProjectV2Create(BaseModel):
    customer_id: int | None = None
    project_type: ProjectTypeValue = "customer"
    name: str = Field(..., min_length=1, max_length=255)
    status: ProjectStatusValue = "active"
    area: str | None = Field(default=None, max_length=128)
    tags: list[str] = Field(default_factory=list)
    start_at: datetime | None = None
    target_end_at: datetime | None = None
    actual_end_at: datetime | None = None

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, v: str | None) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("name cannot be empty")
        return v

    @field_validator("area", mode="before")
    @classmethod
    def normalize_area(cls, v: str | None) -> str | None:
        return normalize_project_name(v)

    @field_validator("start_at", "target_end_at", "actual_end_at", mode="before")
    @classmethod
    def normalize_dt(cls, v: datetime | str | None) -> datetime | None:
        return normalize_datetime_input(v)

    @field_validator("tags", mode="before")
    @classmethod
    def normalize_tags(cls, v: list[str] | None) -> list[str]:
        return normalize_string_list(v)


class ProjectV2Update(BaseModel):
    customer_id: int | None = None
    project_type: ProjectTypeValue | None = None
    name: str | None = Field(default=None, min_length=1, max_length=255)
    status: ProjectStatusValue | None = None
    area: str | None = Field(default=None, max_length=128)
    tags: list[str] | None = None
    start_at: datetime | None = None
    target_end_at: datetime | None = None
    actual_end_at: datetime | None = None
    clear_customer: bool = False

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        if not v:
            raise ValueError("name cannot be empty")
        return v

    @field_validator("area", mode="before")
    @classmethod
    def normalize_area(cls, v: str | None) -> str | None:
        return normalize_project_name(v)

    @field_validator("start_at", "target_end_at", "actual_end_at", mode="before")
    @classmethod
    def normalize_dt(cls, v: datetime | str | None) -> datetime | None:
        return normalize_datetime_input(v)

    @field_validator("tags", mode="before")
    @classmethod
    def normalize_tags(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        return normalize_string_list(v)


class ProjectV2Read(BaseModel):
    id: int
    customer_id: int | None
    project_type: str
    name: str
    status: str
    area: str | None
    tags: list[str]
    start_at: datetime | None
    target_end_at: datetime | None
    actual_end_at: datetime | None
    created_at: datetime
    updated_at: datetime


class FactCreate(BaseModel):
    customer_id: int | None = None
    project_id: int | None = None
    task_id: int | None = None
    fact_date: datetime
    title: str = Field(..., min_length=1, max_length=255)
    raw_markdown: str = Field(..., min_length=1)
    source_type: FactSourceTypeValue = "manual_input"
    value_types: list[str] = Field(default_factory=list)
    status: FactStatusValue = "draft"

    @field_validator("title", mode="before")
    @classmethod
    def normalize_title(cls, v: str | None) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("title cannot be empty")
        return v

    @field_validator("raw_markdown", mode="before")
    @classmethod
    def normalize_raw(cls, v: str | None) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("raw_markdown cannot be empty")
        return v

    @field_validator("fact_date", mode="before")
    @classmethod
    def normalize_dt(cls, v: datetime | str | None) -> datetime:
        dt = normalize_datetime_input(v)
        if dt is None:
            raise ValueError("fact_date is required")
        return dt

    @field_validator("value_types", mode="before")
    @classmethod
    def normalize_vt(cls, v: list[str] | None) -> list[str]:
        return normalize_string_list(v)


class FactUpdate(BaseModel):
    customer_id: int | None = None
    project_id: int | None = None
    task_id: int | None = None
    fact_date: datetime | None = None
    title: str | None = Field(default=None, min_length=1, max_length=255)
    raw_markdown: str | None = None
    source_type: FactSourceTypeValue | None = None
    value_types: list[str] | None = None
    status: FactStatusValue | None = None
    clear_customer: bool = False
    clear_project: bool = False
    clear_task: bool = False

    @field_validator("fact_date", mode="before")
    @classmethod
    def normalize_dt(cls, v: datetime | str | None) -> datetime | None:
        return normalize_datetime_input(v)

    @field_validator("value_types", mode="before")
    @classmethod
    def normalize_vt(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        return normalize_string_list(v)


class FactRead(BaseModel):
    id: int
    customer_id: int | None
    project_id: int | None
    task_id: int | None
    fact_date: datetime
    title: str
    raw_markdown: str
    source_type: str
    value_types: list[str]
    status: str
    created_at: datetime
    updated_at: datetime


class CustomerMaterialFactRead(BaseModel):
    id: int
    material_id: int
    fact_id: int
    sort_order: int
    created_at: datetime


class CustomerMaterialFactCreate(BaseModel):
    fact_id: int
    sort_order: int = 0


class ReviewBatchCreate(BaseModel):
    batch_type: ReviewBatchTypeValue = "weekly_customer_summary"
    title: str = Field(..., min_length=1, max_length=255)
    period_start: datetime | None = None
    period_end: datetime | None = None
    status: ReviewBatchStatusValue = "pending"
    material_count: int = 0
    created_by: str = "manual"

    @field_validator("title", mode="before")
    @classmethod
    def normalize_title(cls, v: str | None) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("title cannot be empty")
        return v

    @field_validator("period_start", "period_end", mode="before")
    @classmethod
    def normalize_dt(cls, v: datetime | str | None) -> datetime | None:
        return normalize_datetime_input(v)


class ReviewBatchUpdate(BaseModel):
    batch_type: ReviewBatchTypeValue | None = None
    title: str | None = Field(default=None, min_length=1, max_length=255)
    period_start: datetime | None = None
    period_end: datetime | None = None
    status: ReviewBatchStatusValue | None = None
    material_count: int | None = None
    created_by: str | None = None

    @field_validator("title", mode="before")
    @classmethod
    def normalize_title(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        if not v:
            raise ValueError("title cannot be empty")
        return v

    @field_validator("period_start", "period_end", mode="before")
    @classmethod
    def normalize_dt(cls, v: datetime | str | None) -> datetime | None:
        return normalize_datetime_input(v)


class ReviewBatchRead(BaseModel):
    id: int
    batch_type: str
    title: str
    period_start: datetime | None
    period_end: datetime | None
    status: str
    material_count: int
    created_by: str
    created_at: datetime
    updated_at: datetime


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
