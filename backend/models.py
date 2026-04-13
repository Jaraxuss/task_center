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


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(UTCDateTimeText(), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=TaskStatus.TODO.value, index=True)
    project: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    tags_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="web")
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
