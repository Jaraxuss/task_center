"""Task domain services.

Covers the full task aggregate: ORM access (load options, 404 helpers,
listing/filtering), serialization, recurrence math, event recording, and
the canonical "wrap fresh task into TaskDetail" helper used by every
mutation endpoint.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from models import EventType, Reminder, ReminderStatus, Task, TaskEvent, TaskRecurrence, TaskStatus
from recurrence import compute_next_recurrence, normalize_days_of_week, normalize_time_of_day
from schemas import (
    ReminderRead,
    TaskDetail,
    TaskEventRead,
    TaskRead,
    TaskRecurrenceRead,
    TaskRecurrenceWrite,
)
from timeutils import now_local, now_utc

# ────────────────────────────────────────────────────────────────────
# Loading
# ────────────────────────────────────────────────────────────────────


def task_load_options() -> tuple[Any, Any, Any]:
    """Eager-load relationships needed to serialize a Task fully."""
    return (selectinload(Task.reminders), selectinload(Task.events), selectinload(Task.recurrence))


def get_task_or_404(db: Session, task_id: int) -> Task:
    stmt = select(Task).where(Task.id == task_id).options(*task_load_options())
    task = db.scalar(stmt)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


def query_tasks(
    db: Session,
    *,
    status: str | None = None,
    query: str | None = None,
    source_type: str | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    customer_id: int | None = None,
    project_id: int | None = None,
):
    stmt = select(Task).options(*task_load_options())
    if status:
        stmt = stmt.where(Task.status == status)
    if query:
        like = f"%{query}%"
        stmt = stmt.where(or_(Task.title.ilike(like), Task.description.ilike(like), Task.project.ilike(like)))
    if source_type:
        stmt = stmt.where(Task.source_type == source_type)
    if created_from is not None:
        stmt = stmt.where(Task.created_at >= created_from)
    if created_to is not None:
        stmt = stmt.where(Task.created_at < created_to)
    if customer_id is not None:
        stmt = stmt.where(Task.customer_id == customer_id)
    if project_id is not None:
        stmt = stmt.where(Task.project_id == project_id)
    return stmt.order_by(Task.due_at.is_(None), Task.due_at.asc(), Task.created_at.desc())


def task_schedule_at(task: Task) -> datetime | None:
    return task.deferred_to or task.due_at


def today_local() -> date:
    return now_local().date()


# ────────────────────────────────────────────────────────────────────
# Serialization
# ────────────────────────────────────────────────────────────────────


def serialize_recurrence(recurrence: TaskRecurrence | None) -> TaskRecurrenceRead | None:
    if recurrence is None:
        return None
    return TaskRecurrenceRead(
        id=recurrence.id,
        task_id=recurrence.task_id,
        enabled=recurrence.enabled,
        frequency=recurrence.frequency,
        interval=recurrence.interval,
        timezone=recurrence.timezone,
        time_of_day=recurrence.time_of_day,
        days_of_week=recurrence.days_of_week or [],
        day_of_month=recurrence.day_of_month,
        start_at=recurrence.start_at,
        end_at=recurrence.end_at,
        next_run_at=recurrence.next_run_at,
        last_run_at=recurrence.last_run_at,
        reminder_offsets_minutes=recurrence.reminder_offsets_minutes or [],
        created_at=recurrence.created_at,
        updated_at=recurrence.updated_at,
    )


def serialize_task(task: Task) -> TaskRead:
    return TaskRead(
        id=task.id,
        title=task.title,
        description=task.description,
        due_at=task.due_at,
        status=task.status,
        project=task.project,
        area=getattr(task, "area", None),
        customer_id=getattr(task, "customer_id", None),
        project_id=getattr(task, "project_id", None),
        tags=task.tags or [],
        source=task.source,
        source_type=getattr(task, "source_type", None),
        created_at=task.created_at,
        updated_at=task.updated_at,
        completed_at=task.completed_at,
        completion_note=task.completion_note,
        canceled_at=task.canceled_at,
        deferred_to=task.deferred_to,
        nightly_bucket=task.nightly_bucket,
        nightly_reviewed_at=task.nightly_reviewed_at,
        reminders=[ReminderRead.model_validate(reminder) for reminder in sorted(task.reminders, key=lambda r: r.remind_at)],
        recurrence=serialize_recurrence(task.recurrence),
    )


def serialize_event(event: TaskEvent) -> TaskEventRead:
    return TaskEventRead(
        id=event.id,
        task_id=event.task_id,
        event_type=event.event_type,
        payload=event.payload or {},
        created_at=event.created_at,
    )


def task_detail_response(db: Session, task_id: int) -> TaskDetail:
    """Re-fetch the task and wrap it into ``TaskDetail`` with sorted events.

    Centralizes the "fetch, serialize, attach events" pattern used by every
    POST/PATCH endpoint that returns ``TaskDetail``.
    """
    task = get_task_or_404(db, task_id)
    detail = serialize_task(task)
    events = [serialize_event(event) for event in sorted(task.events, key=lambda e: e.created_at, reverse=True)]
    return TaskDetail(**detail.model_dump(), events=events)


# ────────────────────────────────────────────────────────────────────
# Events
# ────────────────────────────────────────────────────────────────────


def add_event(db: Session, task: Task, event_type: str, payload: dict[str, Any] | None = None) -> None:
    db.add(
        TaskEvent(
            task_id=task.id,
            event_type=event_type,
            payload=payload or {},
        )
    )


# ────────────────────────────────────────────────────────────────────
# Recurrence
# ────────────────────────────────────────────────────────────────────


def recurrence_event_payload(recurrence: TaskRecurrence) -> dict[str, Any]:
    return {
        "enabled": recurrence.enabled,
        "frequency": recurrence.frequency,
        "interval": recurrence.interval,
        "timezone": recurrence.timezone,
        "time_of_day": recurrence.time_of_day,
        "days_of_week": recurrence.days_of_week or [],
        "day_of_month": recurrence.day_of_month,
        "start_at": recurrence.start_at.isoformat() if recurrence.start_at else None,
        "end_at": recurrence.end_at.isoformat() if recurrence.end_at else None,
        "next_run_at": recurrence.next_run_at.isoformat() if recurrence.next_run_at else None,
        "last_run_at": recurrence.last_run_at.isoformat() if recurrence.last_run_at else None,
        "reminder_offsets_minutes": recurrence.reminder_offsets_minutes or [],
    }


def recurrence_anchor(task: Task, payload: TaskRecurrenceWrite | None = None) -> datetime:
    return (
        (payload.start_at if payload else None)
        or task.due_at
        or (task.recurrence.next_run_at if task.recurrence and task.recurrence.next_run_at else None)
        or now_utc().replace(microsecond=0)
    )


def compute_recurrence_next_run(
    task: Task, recurrence: TaskRecurrence, *, after_dt: datetime | None = None
) -> datetime | None:
    anchor = recurrence.start_at or task.due_at or recurrence.next_run_at or now_utc().replace(microsecond=0)
    return compute_next_recurrence(
        frequency=recurrence.frequency,
        interval=recurrence.interval,
        anchor_at=anchor,
        after_dt=after_dt,
        time_of_day=recurrence.time_of_day,
        days_of_week=recurrence.days_of_week or [],
        day_of_month=recurrence.day_of_month,
        start_at=recurrence.start_at,
        end_at=recurrence.end_at,
        timezone_name=recurrence.timezone,
    )


def upsert_recurrence(db: Session, task: Task, payload: TaskRecurrenceWrite) -> TaskRecurrence:
    recurrence = task.recurrence or TaskRecurrence(task_id=task.id)
    recurrence.enabled = payload.enabled
    recurrence.frequency = payload.frequency
    recurrence.interval = payload.interval
    recurrence.timezone = payload.timezone
    recurrence.time_of_day = normalize_time_of_day(payload.time_of_day)
    recurrence.days_of_week = normalize_days_of_week(payload.days_of_week)
    recurrence.day_of_month = payload.day_of_month
    recurrence.start_at = payload.start_at
    recurrence.end_at = payload.end_at
    recurrence.reminder_offsets_minutes = sorted({int(item) for item in payload.reminder_offsets_minutes})

    anchor = recurrence_anchor(task, payload)
    recurrence.next_run_at = (
        None
        if not payload.enabled
        else compute_next_recurrence(
            frequency=payload.frequency,
            interval=payload.interval,
            anchor_at=anchor,
            after_dt=now_utc().replace(microsecond=0),
            time_of_day=payload.time_of_day,
            days_of_week=payload.days_of_week,
            day_of_month=payload.day_of_month,
            start_at=payload.start_at,
            end_at=payload.end_at,
            timezone_name=payload.timezone,
        )
    )

    if task.recurrence is None:
        task.recurrence = recurrence
    db.add(recurrence)
    db.flush()

    if recurrence.next_run_at:
        task.due_at = recurrence.next_run_at
        task.deferred_to = None
        if task.status in {TaskStatus.DONE.value, TaskStatus.CANCELED.value}:
            task.status = TaskStatus.TODO.value
            task.completed_at = None
            task.canceled_at = None
    return recurrence


def clear_recurrence(task: Task, db: Session) -> None:
    if task.recurrence is not None:
        db.delete(task.recurrence)
        task.recurrence = None


# ────────────────────────────────────────────────────────────────────
# Reminder helper (creating Reminder rows alongside a task)
# ────────────────────────────────────────────────────────────────────


def build_reminder(task: Task, *, remind_at: datetime, channel: str, note: str | None) -> Reminder:
    return Reminder(
        task_id=task.id,
        remind_at=remind_at,
        channel=channel,
        note=note,
        status=ReminderStatus.SCHEDULED.value,
    )


# Re-export for routers that need the EventType enum without re-importing models.
__all__ = [
    "EventType",
    "add_event",
    "build_reminder",
    "clear_recurrence",
    "compute_recurrence_next_run",
    "get_task_or_404",
    "query_tasks",
    "recurrence_anchor",
    "recurrence_event_payload",
    "serialize_event",
    "serialize_recurrence",
    "serialize_task",
    "task_detail_response",
    "task_load_options",
    "task_schedule_at",
    "today_local",
    "upsert_recurrence",
]
