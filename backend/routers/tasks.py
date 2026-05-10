"""Task endpoints (CRUD, lifecycle actions, reminders, related materials)."""

from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from db import get_db
from models import (
    CustomerMaterial,
    EventType,
    Reminder,
    ReminderStatus,
    Task,
    TaskStatus,
)
from schemas import (
    CustomerMaterialRead,
    ReminderCreate,
    TaskActionCancel,
    TaskActionComplete,
    TaskActionDefer,
    TaskCreate,
    TaskDetail,
    TaskRead,
    TaskRecurrenceWrite,
    TaskUpdate,
)
from services.customer_materials import serialize_customer_material
from services.tasks import (
    add_event,
    clear_recurrence,
    compute_recurrence_next_run,
    get_task_or_404,
    query_tasks,
    recurrence_event_payload,
    serialize_task,
    task_detail_response,
    today_local,
    upsert_recurrence,
)
from timeutils import local_day_bounds, now_utc

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.get("", response_model=list[TaskRead])
def list_tasks(
    status: str | None = Query(default=None),
    date_filter: str | None = Query(default=None, alias="date"),
    q: str | None = Query(default=None),
    source_type: str | None = Query(default=None),
    created_from: datetime | None = Query(default=None, alias="from"),
    created_to: datetime | None = Query(default=None, alias="to"),
    customer_id: int | None = Query(default=None),
    project_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[TaskRead]:
    stmt = query_tasks(
        db,
        status=status,
        query=q,
        source_type=source_type,
        created_from=created_from,
        created_to=created_to,
        customer_id=customer_id,
        project_id=project_id,
    )
    if date_filter == "today":
        start, end = local_day_bounds(today_local())
        stmt = stmt.where(Task.due_at.between(start, end - timedelta(microseconds=1)))
    tasks = list(db.scalars(stmt).unique())
    return [serialize_task(task) for task in tasks]


@router.get("/{task_id}", response_model=TaskDetail)
def get_task(task_id: int, db: Session = Depends(get_db)) -> TaskDetail:
    return task_detail_response(db, task_id)


@router.post("", response_model=TaskDetail, status_code=201)
def create_task(payload: TaskCreate, db: Session = Depends(get_db)) -> TaskDetail:
    task = Task(
        title=payload.title,
        description=payload.description,
        due_at=payload.due_at,
        status=TaskStatus.TODO.value,
        area=getattr(payload, "area", None),
        customer_id=getattr(payload, "customer_id", None),
        project_id=getattr(payload, "project_id", None),
        tags=payload.tags,
        source=payload.source,
        source_type=getattr(payload, "source_type", None),
    )
    db.add(task)
    db.flush()
    for reminder_payload in payload.reminders:
        db.add(
            Reminder(
                task_id=task.id,
                remind_at=reminder_payload.remind_at,
                channel=reminder_payload.channel,
                note=reminder_payload.note,
                status=ReminderStatus.SCHEDULED.value,
            )
        )
    if payload.recurrence is not None:
        recurrence = upsert_recurrence(db, task, payload.recurrence)
        add_event(db, task, EventType.RECURRENCE_UPDATED.value, recurrence_event_payload(recurrence))
    add_event(db, task, EventType.CREATED.value, payload.model_dump(mode="json"))
    db.commit()
    db.refresh(task)
    return task_detail_response(db, task.id)


@router.patch("/{task_id}", response_model=TaskDetail)
def update_task(task_id: int, payload: TaskUpdate, db: Session = Depends(get_db)) -> TaskDetail:
    task = get_task_or_404(db, task_id)
    updates = payload.model_dump(exclude_unset=True)
    before = serialize_task(task).model_dump(mode="json")
    if "status" in updates and updates["status"] not in {status.value for status in TaskStatus}:
        raise HTTPException(status_code=400, detail="Invalid status")
    recurrence_payload = updates.pop("recurrence", None)
    clear_recurrence_requested = bool(updates.pop("clear_recurrence", False))
    updates.pop("clear_customer", None)
    updates.pop("clear_project_v2", None)
    updates.pop("project", None)
    for field, value in updates.items():
        setattr(task, field, value)

    next_status = updates.get("status", task.status)
    next_due_at = updates.get("due_at", task.due_at)
    if "due_at" in updates or "status" in updates:
        if next_status == TaskStatus.DEFERRED.value:
            task.deferred_to = next_due_at
        else:
            task.deferred_to = None

    if clear_recurrence_requested:
        clear_recurrence(task, db)
        add_event(db, task, EventType.RECURRENCE_UPDATED.value, {"cleared": True})
    if recurrence_payload is not None:
        recurrence = upsert_recurrence(db, task, TaskRecurrenceWrite.model_validate(recurrence_payload))
        add_event(db, task, EventType.RECURRENCE_UPDATED.value, recurrence_event_payload(recurrence))
    if task.status != TaskStatus.DONE.value:
        task.completed_at = None
        task.completion_note = None
    if task.status != TaskStatus.CANCELED.value:
        task.canceled_at = None
    add_event(
        db,
        task,
        EventType.UPDATED.value,
        {"before": before, "after": payload.model_dump(mode="json", exclude_unset=True)},
    )
    db.commit()
    return task_detail_response(db, task_id)


@router.post("/{task_id}/complete", response_model=TaskDetail)
def complete_task(task_id: int, payload: TaskActionComplete, db: Session = Depends(get_db)) -> TaskDetail:
    task = get_task_or_404(db, task_id)
    completed_at = payload.completed_at or now_utc()
    completion_note = payload.note
    add_event(
        db,
        task,
        EventType.COMPLETED.value,
        {
            "completed_at": completed_at.isoformat(),
            "note": completion_note,
        },
    )

    if task.recurrence and task.recurrence.enabled:
        task.recurrence.last_run_at = completed_at
        recurrence_boundary = max(completed_at, task.due_at or completed_at) + timedelta(seconds=1)
        next_run_at = compute_recurrence_next_run(task, task.recurrence, after_dt=recurrence_boundary)
        task.recurrence.next_run_at = next_run_at
        if next_run_at is None:
            task.status = TaskStatus.DONE.value
            task.completed_at = completed_at
            task.completion_note = completion_note
            add_event(db, task, EventType.STATUS_CHANGED.value, {"status": TaskStatus.DONE.value})
        else:
            previous_due_at = task.due_at
            task.status = TaskStatus.TODO.value
            task.completed_at = None
            task.completion_note = None
            task.canceled_at = None
            task.deferred_to = None
            task.due_at = next_run_at
            add_event(
                db,
                task,
                EventType.RECURRENCE_ADVANCED.value,
                {
                    "completed_at": completed_at.isoformat(),
                    "note": completion_note,
                    "previous_due_at": previous_due_at.isoformat() if previous_due_at else None,
                    "next_run_at": next_run_at.isoformat(),
                },
            )
            add_event(db, task, EventType.STATUS_CHANGED.value, {"status": TaskStatus.TODO.value})
    else:
        task.status = TaskStatus.DONE.value
        task.completed_at = completed_at
        task.completion_note = completion_note
        task.canceled_at = None
        add_event(db, task, EventType.STATUS_CHANGED.value, {"status": TaskStatus.DONE.value})

    db.commit()
    return task_detail_response(db, task_id)


@router.post("/{task_id}/defer", response_model=TaskDetail)
def defer_task(task_id: int, payload: TaskActionDefer, db: Session = Depends(get_db)) -> TaskDetail:
    task = get_task_or_404(db, task_id)
    task.status = TaskStatus.DEFERRED.value
    task.deferred_to = payload.deferred_to
    task.due_at = payload.due_at or payload.deferred_to
    task.completed_at = None
    task.completion_note = None
    if task.recurrence and task.recurrence.enabled:
        task.recurrence.next_run_at = task.due_at
    add_event(db, task, EventType.DEFERRED.value, payload.model_dump(mode="json"))
    add_event(db, task, EventType.STATUS_CHANGED.value, {"status": TaskStatus.DEFERRED.value})
    db.commit()
    return task_detail_response(db, task_id)


@router.post("/{task_id}/cancel", response_model=TaskDetail)
def cancel_task(task_id: int, payload: TaskActionCancel, db: Session = Depends(get_db)) -> TaskDetail:
    task = get_task_or_404(db, task_id)
    canceled_at = payload.canceled_at or now_utc()
    task.status = TaskStatus.CANCELED.value
    task.canceled_at = canceled_at
    task.completed_at = None
    task.completion_note = None
    add_event(
        db,
        task,
        EventType.CANCELED.value,
        {"canceled_at": canceled_at.isoformat(), "reason": payload.reason},
    )
    add_event(db, task, EventType.STATUS_CHANGED.value, {"status": TaskStatus.CANCELED.value})
    db.commit()
    return task_detail_response(db, task_id)


@router.post("/{task_id}/reminders", response_model=TaskDetail, status_code=201)
def create_reminder(task_id: int, payload: ReminderCreate, db: Session = Depends(get_db)) -> TaskDetail:
    task = get_task_or_404(db, task_id)
    reminder = Reminder(
        task_id=task.id,
        remind_at=payload.remind_at,
        channel=payload.channel,
        note=payload.note,
        status=ReminderStatus.SCHEDULED.value,
    )
    db.add(reminder)
    db.flush()
    add_event(
        db,
        task,
        EventType.REMINDER_ADDED.value,
        {"reminder_id": reminder.id, **payload.model_dump(mode="json")},
    )
    db.commit()
    return task_detail_response(db, task_id)


@router.get("/{task_id}/customer-materials", response_model=list[CustomerMaterialRead])
def list_task_customer_materials(
    task_id: int,
    include_archived: bool = False,
    db: Session = Depends(get_db),
) -> list[CustomerMaterialRead]:
    get_task_or_404(db, task_id)
    stmt = select(CustomerMaterial).where(CustomerMaterial.task_id == task_id)
    if not include_archived:
        stmt = stmt.where(CustomerMaterial.archived_at.is_(None))
    stmt = stmt.order_by(CustomerMaterial.updated_at.desc(), CustomerMaterial.id.desc())
    return [serialize_customer_material(material) for material in db.scalars(stmt).all()]
