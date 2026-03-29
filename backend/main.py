from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from config import get_settings
from db import Base, engine, get_db
from models import EventType, Reminder, ReminderStatus, Task, TaskEvent, TaskRecurrence, TaskStatus
from recurrence import compute_next_recurrence, normalize_days_of_week, normalize_time_of_day
from schemas import (
    BoardSummary,
    DashboardPayload,
    HealthResponse,
    HistorySummary,
    NightlyReviewPlaceholder,
    PlanGroup,
    ProjectRenameRequest,
    ProjectRenameResponse,
    ProjectSummary,
    ReminderCreate,
    ReminderRead,
    TaskActionCancel,
    TaskActionComplete,
    TaskActionDefer,
    TaskBoardGroup,
    TaskCreate,
    TaskDetail,
    TaskEventRead,
    TaskRead,
    TaskRecurrenceRead,
    TaskRecurrenceWrite,
    TaskUpdate,
    TodaySummary,
)

settings = get_settings()

app = FastAPI(title="Task Center Backend", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
DB_PATH = Path(__file__).resolve().parent / "data" / "task_center.db"


@app.on_event("startup")
def on_startup() -> None:
    init_db()



def init_db() -> None:
    Base.metadata.create_all(bind=engine)



def recurrence_event_payload(recurrence: TaskRecurrence) -> dict[str, Any]:
    return {
        "enabled": recurrence.enabled,
        "frequency": recurrence.frequency,
        "interval": recurrence.interval,
        "timezone": recurrence.timezone,
        "time_of_day": recurrence.time_of_day,
        "days_of_week": json.loads(recurrence.days_of_week_json or "[]"),
        "day_of_month": recurrence.day_of_month,
        "start_at": recurrence.start_at.isoformat() if recurrence.start_at else None,
        "end_at": recurrence.end_at.isoformat() if recurrence.end_at else None,
        "next_run_at": recurrence.next_run_at.isoformat() if recurrence.next_run_at else None,
        "last_run_at": recurrence.last_run_at.isoformat() if recurrence.last_run_at else None,
        "reminder_offsets_minutes": json.loads(recurrence.reminder_offsets_json or "[]"),
    }



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
        days_of_week=json.loads(recurrence.days_of_week_json or "[]"),
        day_of_month=recurrence.day_of_month,
        start_at=recurrence.start_at,
        end_at=recurrence.end_at,
        next_run_at=recurrence.next_run_at,
        last_run_at=recurrence.last_run_at,
        reminder_offsets_minutes=json.loads(recurrence.reminder_offsets_json or "[]"),
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
        tags=json.loads(task.tags_json or "[]"),
        source=task.source,
        created_at=task.created_at,
        updated_at=task.updated_at,
        completed_at=task.completed_at,
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
        payload=json.loads(event.payload_json or "{}"),
        created_at=event.created_at,
    )



def add_event(db: Session, task: Task, event_type: str, payload: dict[str, Any] | None = None) -> None:
    db.add(
        TaskEvent(
            task_id=task.id,
            event_type=event_type,
            payload_json=json.dumps(payload or {}, ensure_ascii=False),
        )
    )



def task_load_options():
    return (selectinload(Task.reminders), selectinload(Task.events), selectinload(Task.recurrence))



def get_task_or_404(db: Session, task_id: int) -> Task:
    stmt = select(Task).where(Task.id == task_id).options(*task_load_options())
    task = db.scalar(stmt)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task



def query_tasks(db: Session, *, status: str | None = None, query: str | None = None):
    stmt = select(Task).options(*task_load_options())
    if status:
        stmt = stmt.where(Task.status == status)
    if query:
        like = f"%{query}%"
        stmt = stmt.where(or_(Task.title.ilike(like), Task.description.ilike(like), Task.project.ilike(like)))
    return stmt.order_by(Task.due_at.is_(None), Task.due_at.asc(), Task.created_at.desc())



def day_range(target: date) -> tuple[datetime, datetime]:
    start = datetime.combine(target, time.min)
    end = start + timedelta(days=1)
    return start, end



def task_schedule_at(task: Task) -> datetime | None:
    return task.deferred_to or task.due_at



def recurrence_anchor(task: Task, payload: TaskRecurrenceWrite | None = None) -> datetime:
    return (
        (payload.start_at if payload else None)
        or task.due_at
        or (task.recurrence.next_run_at if task.recurrence and task.recurrence.next_run_at else None)
        or datetime.utcnow().replace(microsecond=0)
    )



def compute_recurrence_next_run(task: Task, recurrence: TaskRecurrence, *, after_dt: datetime | None = None) -> datetime | None:
    anchor = recurrence.start_at or task.due_at or recurrence.next_run_at or datetime.utcnow().replace(microsecond=0)
    return compute_next_recurrence(
        frequency=recurrence.frequency,
        interval=recurrence.interval,
        anchor_at=anchor,
        after_dt=after_dt,
        time_of_day=recurrence.time_of_day,
        days_of_week=json.loads(recurrence.days_of_week_json or "[]"),
        day_of_month=recurrence.day_of_month,
        start_at=recurrence.start_at,
        end_at=recurrence.end_at,
    )



def upsert_recurrence(db: Session, task: Task, payload: TaskRecurrenceWrite) -> TaskRecurrence:
    recurrence = task.recurrence or TaskRecurrence(task_id=task.id)
    recurrence.enabled = payload.enabled
    recurrence.frequency = payload.frequency
    recurrence.interval = payload.interval
    recurrence.timezone = payload.timezone
    recurrence.time_of_day = normalize_time_of_day(payload.time_of_day)
    recurrence.days_of_week_json = json.dumps(normalize_days_of_week(payload.days_of_week), ensure_ascii=False)
    recurrence.day_of_month = payload.day_of_month
    recurrence.start_at = payload.start_at
    recurrence.end_at = payload.end_at
    recurrence.reminder_offsets_json = json.dumps(sorted({int(item) for item in payload.reminder_offsets_minutes}), ensure_ascii=False)

    anchor = recurrence_anchor(task, payload)
    recurrence.next_run_at = None if not payload.enabled else compute_next_recurrence(
        frequency=payload.frequency,
        interval=payload.interval,
        anchor_at=anchor,
        after_dt=datetime.utcnow().replace(microsecond=0),
        time_of_day=payload.time_of_day,
        days_of_week=payload.days_of_week,
        day_of_month=payload.day_of_month,
        start_at=payload.start_at,
        end_at=payload.end_at,
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



def build_plan_groups(db: Session) -> list[PlanGroup]:
    not_started_statuses = [TaskStatus.TODO.value, TaskStatus.DEFERRED.value]
    schedule_at = func.coalesce(Task.deferred_to, Task.due_at)
    tasks = list(
        db.scalars(
            select(Task)
            .where(Task.status.in_(not_started_statuses))
            .options(*task_load_options())
            .order_by(schedule_at.is_(None), schedule_at.asc(), Task.created_at.asc())
        ).unique()
    )

    grouped: dict[date | None, list[Task]] = {}
    for task in tasks:
        schedule_value = task_schedule_at(task)
        grouped.setdefault(schedule_value.date() if schedule_value else None, []).append(task)

    sorted_dates = sorted(group_date for group_date in grouped.keys() if group_date is not None)
    if None in grouped:
        sorted_dates.append(None)

    plan_groups: list[PlanGroup] = []
    for group_date in sorted_dates:
        group_tasks = sorted(
            grouped[group_date],
            key=lambda task: (task_schedule_at(task) is None, task_schedule_at(task) or datetime.max, task.created_at),
        )
        plan_groups.append(
            PlanGroup(
                key=group_date.isoformat() if group_date else "unscheduled",
                title=group_date.isoformat() if group_date else "未安排",
                group_date=group_date,
                tasks=[serialize_task(task) for task in group_tasks],
            )
        )

    return plan_groups



def build_today_summary(db: Session, target: date | None = None) -> TodaySummary:
    target = target or date.today()
    start, end = day_range(target)
    stmt = (
        select(Task)
        .where(
            or_(
                Task.due_at.between(start, end - timedelta(microseconds=1)),
                Task.deferred_to.between(start, end - timedelta(microseconds=1)),
            )
        )
        .options(*task_load_options())
        .order_by(Task.due_at.is_(None), Task.due_at.asc(), Task.created_at.asc())
    )
    tasks = list(db.scalars(stmt).unique())
    items = [serialize_task(task) for task in tasks]
    open_statuses = {TaskStatus.TODO.value, TaskStatus.DOING.value, TaskStatus.DEFERRED.value}
    return TodaySummary(
        date=target,
        tasks=items,
        total=len(items),
        open_count=sum(1 for item in items if item.status in open_statuses),
        completed_count=sum(1 for item in items if item.status == TaskStatus.DONE.value),
        plan_groups=build_plan_groups(db),
    )



def build_board_summary(db: Session) -> BoardSummary:
    status_order = [
        TaskStatus.TODO.value,
        TaskStatus.DOING.value,
        TaskStatus.DEFERRED.value,
        TaskStatus.DONE.value,
        TaskStatus.CANCELED.value,
    ]
    tasks = list(db.scalars(query_tasks(db)).unique())
    grouped: list[TaskBoardGroup] = []
    for status in status_order:
        grouped.append(TaskBoardGroup(status=status, tasks=[serialize_task(task) for task in tasks if task.status == status]))
    return BoardSummary(groups=grouped)



def build_history_summary(db: Session, *, target: date | None = None, status: str | None = None, query: str | None = None) -> HistorySummary:
    stmt = query_tasks(db, status=status, query=query)
    if target:
        start, end = day_range(target)
        stmt = stmt.where(
            or_(
                Task.created_at.between(start, end - timedelta(microseconds=1)),
                Task.completed_at.between(start, end - timedelta(microseconds=1)),
                Task.canceled_at.between(start, end - timedelta(microseconds=1)),
                Task.deferred_to.between(start, end - timedelta(microseconds=1)),
            )
        )
    tasks = list(db.scalars(stmt).unique())
    items = [serialize_task(task) for task in tasks]
    return HistorySummary(tasks=items, total=len(items))



def build_project_summaries(db: Session) -> list[ProjectSummary]:
    tasks = list(db.scalars(select(Task).where(Task.project.is_not(None))).unique())
    grouped: dict[str, list[Task]] = {}
    for task in tasks:
        if not task.project:
            continue
        grouped.setdefault(task.project, []).append(task)

    open_statuses = {TaskStatus.TODO.value, TaskStatus.DOING.value, TaskStatus.DEFERRED.value}
    return sorted(
        [
            ProjectSummary(
                name=project_name,
                task_count=len(project_tasks),
                open_task_count=sum(1 for task in project_tasks if task.status in open_statuses),
                done_task_count=sum(1 for task in project_tasks if task.status == TaskStatus.DONE.value),
            )
            for project_name, project_tasks in grouped.items()
        ],
        key=lambda item: (-item.open_task_count, -item.task_count, item.name),
    )


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", db=str(DB_PATH), now=datetime.utcnow())


@app.get("/api/tasks", response_model=list[TaskRead])
def list_tasks(
    status: str | None = Query(default=None),
    date_filter: str | None = Query(default=None, alias="date"),
    q: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[TaskRead]:
    stmt = query_tasks(db, status=status, query=q)
    if date_filter == "today":
        start, end = day_range(date.today())
        stmt = stmt.where(Task.due_at.between(start, end - timedelta(microseconds=1)))
    tasks = list(db.scalars(stmt).unique())
    return [serialize_task(task) for task in tasks]


@app.get("/api/projects", response_model=list[ProjectSummary])
def list_projects(db: Session = Depends(get_db)) -> list[ProjectSummary]:
    return build_project_summaries(db)


@app.patch("/api/projects/rename", response_model=ProjectRenameResponse)
def rename_project(payload: ProjectRenameRequest, db: Session = Depends(get_db)) -> ProjectRenameResponse:
    if payload.old_name == payload.new_name:
        raise HTTPException(status_code=400, detail="Project name is unchanged")

    tasks = list(
        db.scalars(select(Task).where(Task.project == payload.old_name).options(*task_load_options())).unique()
    )
    if not tasks:
        raise HTTPException(status_code=404, detail="Project not found")

    for task in tasks:
        task.project = payload.new_name
        add_event(
            db,
            task,
            EventType.PROJECT_RENAMED.value,
            {"old_name": payload.old_name, "new_name": payload.new_name},
        )

    db.commit()
    project_summary = next((item for item in build_project_summaries(db) if item.name == payload.new_name), None)
    if project_summary is None:
        raise HTTPException(status_code=500, detail="Project rename persisted but summary lookup failed")

    return ProjectRenameResponse(
        old_name=payload.old_name,
        new_name=payload.new_name,
        updated_task_count=len(tasks),
        project=project_summary,
    )


@app.get("/api/tasks/{task_id}", response_model=TaskDetail)
def get_task(task_id: int, db: Session = Depends(get_db)) -> TaskDetail:
    task = get_task_or_404(db, task_id)
    detail = serialize_task(task)
    return TaskDetail(**detail.model_dump(), events=[serialize_event(event) for event in sorted(task.events, key=lambda e: e.created_at, reverse=True)])


@app.post("/api/tasks", response_model=TaskDetail, status_code=201)
def create_task(payload: TaskCreate, db: Session = Depends(get_db)) -> TaskDetail:
    task = Task(
        title=payload.title,
        description=payload.description,
        due_at=payload.due_at,
        status=TaskStatus.TODO.value,
        project=payload.project,
        tags_json=json.dumps(payload.tags, ensure_ascii=False),
        source=payload.source,
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
    task = get_task_or_404(db, task.id)
    detail = serialize_task(task)
    return TaskDetail(**detail.model_dump(), events=[serialize_event(event) for event in sorted(task.events, key=lambda e: e.created_at, reverse=True)])


@app.patch("/api/tasks/{task_id}", response_model=TaskDetail)
def update_task(task_id: int, payload: TaskUpdate, db: Session = Depends(get_db)) -> TaskDetail:
    task = get_task_or_404(db, task_id)
    updates = payload.model_dump(exclude_unset=True)
    before = serialize_task(task).model_dump(mode="json")
    if "status" in updates and updates["status"] not in {status.value for status in TaskStatus}:
        raise HTTPException(status_code=400, detail="Invalid status")
    recurrence_payload = updates.pop("recurrence", None)
    clear_recurrence_requested = bool(updates.pop("clear_recurrence", False))
    if "tags" in updates:
        task.tags_json = json.dumps(updates.pop("tags"), ensure_ascii=False)
    for field, value in updates.items():
        setattr(task, field, value)
    if clear_recurrence_requested:
        clear_recurrence(task, db)
        add_event(db, task, EventType.RECURRENCE_UPDATED.value, {"cleared": True})
    if recurrence_payload is not None:
        recurrence = upsert_recurrence(db, task, TaskRecurrenceWrite.model_validate(recurrence_payload))
        add_event(db, task, EventType.RECURRENCE_UPDATED.value, recurrence_event_payload(recurrence))
    if task.status != TaskStatus.DONE.value:
        task.completed_at = None
    if task.status != TaskStatus.CANCELED.value:
        task.canceled_at = None
    add_event(db, task, EventType.UPDATED.value, {"before": before, "after": payload.model_dump(mode="json", exclude_unset=True)})
    db.commit()
    task = get_task_or_404(db, task_id)
    detail = serialize_task(task)
    return TaskDetail(**detail.model_dump(), events=[serialize_event(event) for event in sorted(task.events, key=lambda e: e.created_at, reverse=True)])


@app.post("/api/tasks/{task_id}/complete", response_model=TaskDetail)
def complete_task(task_id: int, payload: TaskActionComplete, db: Session = Depends(get_db)) -> TaskDetail:
    task = get_task_or_404(db, task_id)
    completed_at = payload.completed_at or datetime.utcnow()
    add_event(db, task, EventType.COMPLETED.value, {"completed_at": completed_at.isoformat()})

    if task.recurrence and task.recurrence.enabled:
        task.recurrence.last_run_at = completed_at
        recurrence_boundary = max(completed_at, task.due_at or completed_at) + timedelta(seconds=1)
        next_run_at = compute_recurrence_next_run(task, task.recurrence, after_dt=recurrence_boundary)
        task.recurrence.next_run_at = next_run_at
        if next_run_at is None:
            task.status = TaskStatus.DONE.value
            task.completed_at = completed_at
            add_event(db, task, EventType.STATUS_CHANGED.value, {"status": TaskStatus.DONE.value})
        else:
            previous_due_at = task.due_at
            task.status = TaskStatus.TODO.value
            task.completed_at = None
            task.canceled_at = None
            task.deferred_to = None
            task.due_at = next_run_at
            add_event(
                db,
                task,
                EventType.RECURRENCE_ADVANCED.value,
                {
                    "completed_at": completed_at.isoformat(),
                    "previous_due_at": previous_due_at.isoformat() if previous_due_at else None,
                    "next_run_at": next_run_at.isoformat(),
                },
            )
            add_event(db, task, EventType.STATUS_CHANGED.value, {"status": TaskStatus.TODO.value})
    else:
        task.status = TaskStatus.DONE.value
        task.completed_at = completed_at
        task.canceled_at = None
        add_event(db, task, EventType.STATUS_CHANGED.value, {"status": TaskStatus.DONE.value})

    db.commit()
    task = get_task_or_404(db, task_id)
    detail = serialize_task(task)
    return TaskDetail(**detail.model_dump(), events=[serialize_event(event) for event in sorted(task.events, key=lambda e: e.created_at, reverse=True)])


@app.post("/api/tasks/{task_id}/defer", response_model=TaskDetail)
def defer_task(task_id: int, payload: TaskActionDefer, db: Session = Depends(get_db)) -> TaskDetail:
    task = get_task_or_404(db, task_id)
    task.status = TaskStatus.DEFERRED.value
    task.deferred_to = payload.deferred_to
    task.due_at = payload.due_at or payload.deferred_to
    task.completed_at = None
    if task.recurrence and task.recurrence.enabled:
        task.recurrence.next_run_at = task.due_at
    add_event(db, task, EventType.DEFERRED.value, payload.model_dump(mode="json"))
    add_event(db, task, EventType.STATUS_CHANGED.value, {"status": TaskStatus.DEFERRED.value})
    db.commit()
    task = get_task_or_404(db, task_id)
    detail = serialize_task(task)
    return TaskDetail(**detail.model_dump(), events=[serialize_event(event) for event in sorted(task.events, key=lambda e: e.created_at, reverse=True)])


@app.post("/api/tasks/{task_id}/cancel", response_model=TaskDetail)
def cancel_task(task_id: int, payload: TaskActionCancel, db: Session = Depends(get_db)) -> TaskDetail:
    task = get_task_or_404(db, task_id)
    canceled_at = payload.canceled_at or datetime.utcnow()
    task.status = TaskStatus.CANCELED.value
    task.canceled_at = canceled_at
    task.completed_at = None
    add_event(db, task, EventType.CANCELED.value, {"canceled_at": canceled_at.isoformat(), "reason": payload.reason})
    add_event(db, task, EventType.STATUS_CHANGED.value, {"status": TaskStatus.CANCELED.value})
    db.commit()
    task = get_task_or_404(db, task_id)
    detail = serialize_task(task)
    return TaskDetail(**detail.model_dump(), events=[serialize_event(event) for event in sorted(task.events, key=lambda e: e.created_at, reverse=True)])


@app.post("/api/tasks/{task_id}/reminders", response_model=TaskDetail, status_code=201)
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
    add_event(db, task, EventType.REMINDER_ADDED.value, {"reminder_id": reminder.id, **payload.model_dump(mode="json")})
    db.commit()
    task = get_task_or_404(db, task_id)
    detail = serialize_task(task)
    return TaskDetail(**detail.model_dump(), events=[serialize_event(event) for event in sorted(task.events, key=lambda e: e.created_at, reverse=True)])


@app.get("/api/history", response_model=HistorySummary)
def history(
    date_value: date | None = Query(default=None, alias="date"),
    status: str | None = Query(default=None),
    q: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> HistorySummary:
    return build_history_summary(db, target=date_value, status=status, query=q)


@app.get("/api/dashboard/today", response_model=TodaySummary)
def dashboard_today(db: Session = Depends(get_db)) -> TodaySummary:
    return build_today_summary(db)


@app.get("/api/dashboard/board", response_model=BoardSummary)
def dashboard_board(db: Session = Depends(get_db)) -> BoardSummary:
    return build_board_summary(db)


@app.get("/api/dashboard/history", response_model=HistorySummary)
def dashboard_history(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> HistorySummary:
    summary = build_history_summary(db)
    summary.tasks = summary.tasks[:limit]
    summary.total = len(summary.tasks)
    return summary


@app.get("/api/dashboard", response_model=DashboardPayload)
def dashboard(db: Session = Depends(get_db)) -> DashboardPayload:
    return DashboardPayload(
        today=build_today_summary(db),
        board=build_board_summary(db),
        history=build_history_summary(db),
    )


@app.get("/api/nightly-review", response_model=NightlyReviewPlaceholder)
def nightly_review_placeholder(db: Session = Depends(get_db)) -> NightlyReviewPlaceholder:
    pending_count = db.scalar(
        select(func.count(Task.id)).where(
            Task.status.in_([TaskStatus.TODO.value, TaskStatus.DOING.value, TaskStatus.DEFERRED.value])
        )
    ) or 0
    return NightlyReviewPlaceholder(
        note="22:00 晚间收口流程暂未实现自动执行，但已保留 nightly_bucket/nightly_reviewed_at 与 nightly_reviewed 事件类型供后续 cron/聊天指令接入。重复任务已支持 recurrence 配置与下一次触发时间计算。",
        pending_candidates=pending_count,
    )


if __name__ == "__main__":
    import uvicorn

    init_db()
    uvicorn.run("main:app", host=settings.api_host, port=settings.api_port, reload=True)
