from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db import Base


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


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=TaskStatus.TODO.value, index=True)
    project: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    tags_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="web")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, server_default=func.now(), onupdate=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    deferred_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    nightly_bucket: Mapped[str | None] = mapped_column(String(32), nullable=True, default="open")
    nightly_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)

    reminders: Mapped[list[Reminder]] = relationship("Reminder", back_populates="task", cascade="all, delete-orphan")
    events: Mapped[list[TaskEvent]] = relationship("TaskEvent", back_populates="task", cascade="all, delete-orphan")


class Reminder(Base):
    __tablename__ = "reminders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    remind_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(32), nullable=False, default="local")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=ReminderStatus.SCHEDULED.value, index=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, server_default=func.now(), onupdate=func.now())

    task: Mapped[Task] = relationship("Task", back_populates="reminders")


class TaskEvent(Base):
    __tablename__ = "task_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, server_default=func.now(), index=True)

    task: Mapped[Task] = relationship("Task", back_populates="events")
