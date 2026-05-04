from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

from db import Base
from timeutils import APP_TIMEZONE, now_utc, parse_datetime_string, to_storage_string, to_utc_datetime


class UTCDateTimeText(TypeDecorator):
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return to_storage_string(value, assume_tz=APP_TIMEZONE)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, datetime):
            return to_utc_datetime(value, assume_tz=APP_TIMEZONE)
        return to_utc_datetime(parse_datetime_string(value), assume_tz=APP_TIMEZONE)


class TaskStatus(str, Enum):
    TODO = "todo"
    DOING = "doing"
    DONE = "done"
    DEFERRED = "deferred"
    CANCELED = "canceled"


class TaskSourceType(str, Enum):
    """任务来源标签。

    仅作分类标签使用，不存原文内容。原文内容仅存在 ``Fact.raw_markdown`` 一处。

    转发/截图/会议纪要场景下，OpenClaw 主代理必须在 ``POST /api/tasks`` 时带上对应
    枚举值，并配套 ``POST /api/facts`` 写入原始内容（参考 ``task-center-customer-knowledge``
    SKILL）。本枚举仅作推荐值，未来可在不迁移数据库的前提下扩展。
    """

    USER_CHAT = "user_chat"
    FORWARDED_MESSAGE = "forwarded_message"
    SCREENSHOT = "screenshot"
    MEETING_NOTE = "meeting_note"
    MANUAL_INPUT = "manual_input"


class CustomerStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    CLOSED = "closed"


class ProjectStatus(str, Enum):
    ACTIVE = "active"
    WAITING = "waiting"
    DONE = "done"
    CANCELED = "canceled"


class ProjectType(str, Enum):
    CUSTOMER = "customer"
    PERSONAL = "personal"
    INTERNAL = "internal"


class FactStatus(str, Enum):
    DRAFT = "draft"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class FactSourceType(str, Enum):
    CHAT = "chat"
    SCREENSHOT_OCR = "screenshot_ocr"
    TASK_COMPLETION = "task_completion"
    MEETING_NOTE = "meeting_note"
    MANUAL_INPUT = "manual_input"
    FORWARDED_MESSAGE = "forwarded_message"
    DOCUMENT = "document"


class MaterialType(str, Enum):
    PERIOD_SUMMARY = "period_summary"
    FACT_BUNDLE = "fact_bundle"
    MEETING_NOTE = "meeting_note"
    PROJECT_DIGEST = "project_digest"


class ReviewBatchStatus(str, Enum):
    PENDING = "pending"
    PARTIAL = "partial"
    APPROVED = "approved"
    UPLOADED = "uploaded"


class ReviewBatchType(str, Enum):
    WEEKLY_CUSTOMER_SUMMARY = "weekly_customer_summary"
    DAILY_CUSTOMER_SUMMARY = "daily_customer_summary"
    MANUAL_GENERATION = "manual_generation"


class CustomerMaterialStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    SKIPPED = "skipped"
    UPLOADED = "uploaded"


class ReminderStatus(str, Enum):
    SCHEDULED = "scheduled"
    FIRED = "fired"
    CANCELED = "canceled"


class EventType(str, Enum):
    CREATED = "created"
    UPDATED = "updated"
    STATUS_CHANGED = "status_changed"
    REMINDER_ADDED = "reminder_added"
    REMINDER_FIRED = "reminder_fired"
    DEFERRED = "deferred"
    COMPLETED = "completed"
    CANCELED = "canceled"
    PROJECT_RENAMED = "project_renamed"
    NIGHTLY_REVIEWED = "nightly_reviewed"
    RECURRENCE_UPDATED = "recurrence_updated"
    RECURRENCE_ADVANCED = "recurrence_advanced"


class CustomerMaterialFact(Base):
    __tablename__ = "customer_material_facts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    material_id: Mapped[int] = mapped_column(ForeignKey("customer_materials.id", ondelete="CASCADE"), nullable=False, index=True)
    fact_id: Mapped[int] = mapped_column(ForeignKey("facts.id", ondelete="CASCADE"), nullable=False, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(UTCDateTimeText(), nullable=False, default=now_utc)


class ReviewBatch(Base):
    __tablename__ = "review_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    batch_type: Mapped[str] = mapped_column(String(32), nullable=False, default=ReviewBatchType.WEEKLY_CUSTOMER_SUMMARY.value, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    period_start: Mapped[datetime | None] = mapped_column(UTCDateTimeText(), nullable=True)
    period_end: Mapped[datetime | None] = mapped_column(UTCDateTimeText(), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=ReviewBatchStatus.PENDING.value, index=True)
    material_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_by: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")
    created_at: Mapped[datetime] = mapped_column(UTCDateTimeText(), nullable=False, default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTimeText(), nullable=False, default=now_utc, onupdate=now_utc)

    materials: Mapped[list[CustomerMaterial]] = relationship("CustomerMaterial", back_populates="review_batch")


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    key: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
    aliases_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=CustomerStatus.ACTIVE.value, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    area: Mapped[str | None] = mapped_column(String(128), nullable=True)
    tags_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    created_at: Mapped[datetime] = mapped_column(UTCDateTimeText(), nullable=False, default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTimeText(), nullable=False, default=now_utc, onupdate=now_utc)

    projects: Mapped[list["Project"]] = relationship("Project", back_populates="customer")


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id", ondelete="SET NULL"), nullable=True, index=True)
    project_type: Mapped[str] = mapped_column(String(32), nullable=False, default=ProjectType.CUSTOMER.value)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=ProjectStatus.ACTIVE.value, index=True)
    area: Mapped[str | None] = mapped_column(String(128), nullable=True)
    tags_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    start_at: Mapped[datetime | None] = mapped_column(UTCDateTimeText(), nullable=True)
    target_end_at: Mapped[datetime | None] = mapped_column(UTCDateTimeText(), nullable=True)
    actual_end_at: Mapped[datetime | None] = mapped_column(UTCDateTimeText(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTimeText(), nullable=False, default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTimeText(), nullable=False, default=now_utc, onupdate=now_utc)

    customer: Mapped[Customer | None] = relationship("Customer", back_populates="projects")


class Fact(Base):
    __tablename__ = "facts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id", ondelete="SET NULL"), nullable=True, index=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)
    task_id: Mapped[int | None] = mapped_column(ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True, index=True)
    fact_date: Mapped[datetime] = mapped_column(UTCDateTimeText(), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    raw_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, default=FactSourceType.MANUAL_INPUT.value, index=True)
    value_types_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=FactStatus.DRAFT.value, index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTimeText(), nullable=False, default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTimeText(), nullable=False, default=now_utc, onupdate=now_utc)


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(UTCDateTimeText(), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=TaskStatus.TODO.value, index=True)
    project: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    area: Mapped[str | None] = mapped_column(String(128), nullable=True)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id", ondelete="SET NULL"), nullable=True, index=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)
    tags_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="web")
    source_type: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTimeText(), nullable=False, default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTimeText(), nullable=False, default=now_utc, onupdate=now_utc)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTimeText(), nullable=True)
    completion_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    canceled_at: Mapped[datetime | None] = mapped_column(UTCDateTimeText(), nullable=True)
    deferred_to: Mapped[datetime | None] = mapped_column(UTCDateTimeText(), nullable=True)
    nightly_bucket: Mapped[str | None] = mapped_column(String(32), nullable=True, default="open")
    nightly_reviewed_at: Mapped[datetime | None] = mapped_column(UTCDateTimeText(), nullable=True)

    reminders: Mapped[list[Reminder]] = relationship("Reminder", back_populates="task", cascade="all, delete-orphan")
    events: Mapped[list[TaskEvent]] = relationship("TaskEvent", back_populates="task", cascade="all, delete-orphan")
    recurrence: Mapped[TaskRecurrence | None] = relationship("TaskRecurrence", back_populates="task", cascade="all, delete-orphan", uselist=False)
    customer_materials: Mapped[list[CustomerMaterial]] = relationship("CustomerMaterial", back_populates="task")


class CustomerMaterial(Base):
    __tablename__ = "customer_materials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    # Legacy metadata fields (kept for backward compatibility)
    project: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, default="text", index=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="chat")
    source_refs_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    value_types_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    task_id: Mapped[int | None] = mapped_column(ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True, index=True)
    archived_at: Mapped[datetime | None] = mapped_column(UTCDateTimeText(), nullable=True, index=True)
    # V2 fields
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    material_date: Mapped[datetime | None] = mapped_column(UTCDateTimeText(), nullable=True, index=True)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id", ondelete="SET NULL"), nullable=True, index=True)
    project_v2_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)
    review_batch_id: Mapped[int | None] = mapped_column(ForeignKey("review_batches.id", ondelete="SET NULL"), nullable=True, index=True)
    material_type: Mapped[str] = mapped_column(String(32), nullable=False, default="period_summary")
    period_start: Mapped[datetime | None] = mapped_column(UTCDateTimeText(), nullable=True)
    period_end: Mapped[datetime | None] = mapped_column(UTCDateTimeText(), nullable=True)
    raw_facts_markdown: Mapped[str | None] = mapped_column(Text, nullable=True)
    generation_meta_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=CustomerMaterialStatus.PENDING.value, index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTimeText(), nullable=False, default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTimeText(), nullable=False, default=now_utc, onupdate=now_utc)

    task: Mapped[Task | None] = relationship("Task", back_populates="customer_materials")
    review_batch: Mapped[ReviewBatch | None] = relationship("ReviewBatch", back_populates="materials")


class Reminder(Base):
    __tablename__ = "reminders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    remind_at: Mapped[datetime] = mapped_column(UTCDateTimeText(), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(32), nullable=False, default="local")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=ReminderStatus.SCHEDULED.value, index=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTimeText(), nullable=False, default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTimeText(), nullable=False, default=now_utc, onupdate=now_utc)

    task: Mapped[Task] = relationship("Task", back_populates="reminders")


class TaskRecurrence(Base):
    __tablename__ = "task_recurrences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    frequency: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    interval: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="Asia/Shanghai")
    time_of_day: Mapped[str | None] = mapped_column(String(16), nullable=True)
    days_of_week_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    day_of_month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    start_at: Mapped[datetime | None] = mapped_column(UTCDateTimeText(), nullable=True)
    end_at: Mapped[datetime | None] = mapped_column(UTCDateTimeText(), nullable=True)
    next_run_at: Mapped[datetime | None] = mapped_column(UTCDateTimeText(), nullable=True, index=True)
    last_run_at: Mapped[datetime | None] = mapped_column(UTCDateTimeText(), nullable=True)
    reminder_offsets_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    created_at: Mapped[datetime] = mapped_column(UTCDateTimeText(), nullable=False, default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTimeText(), nullable=False, default=now_utc, onupdate=now_utc)

    task: Mapped[Task] = relationship("Task", back_populates="recurrence")


class TaskEvent(Base):
    __tablename__ = "task_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(UTCDateTimeText(), nullable=False, default=now_utc, index=True)

    task: Mapped[Task] = relationship("Task", back_populates="events")


class BoardPreference(Base):
    __tablename__ = "board_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    task_order_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    pinned_projects_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    project_order_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    created_at: Mapped[datetime] = mapped_column(UTCDateTimeText(), nullable=False, default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTimeText(), nullable=False, default=now_utc, onupdate=now_utc)
