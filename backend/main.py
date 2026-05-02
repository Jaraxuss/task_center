from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, selectinload

from config import get_settings
from db import Base, engine, get_db
from models import BoardPreference, CustomerMaterial, CustomerMaterialStatus, EventType, Reminder, ReminderStatus, Task, TaskEvent, TaskRecurrence, TaskStatus
from recurrence import compute_next_recurrence, normalize_days_of_week, normalize_time_of_day
from timeutils import APP_TIMEZONE, UTC, local_date, local_day_bounds, now_local, now_utc, parse_datetime_string, to_storage_string
from schemas import (
    BoardPreferenceRead,
    BoardPreferenceUpdate,
    BoardSummary,
    CustomerMaterialCreate,
    CustomerMaterialRead,
    CustomerMaterialUpdate,
    DashboardPayload,
    HealthResponse,
    HistorySummary,
    NightlyReviewPlaceholder,
    PlanGroup,
    PlanSummary,
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
    normalize_project_name,
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
DATETIME_COLUMNS: dict[str, list[str]] = {
    "tasks": ["due_at", "created_at", "updated_at", "completed_at", "canceled_at", "deferred_to", "nightly_reviewed_at"],
    "reminders": ["remind_at", "created_at", "updated_at"],
    "task_recurrences": ["start_at", "end_at", "next_run_at", "last_run_at", "created_at", "updated_at"],
    "task_events": ["created_at"],
    "customer_materials": ["material_date", "created_at", "updated_at", "archived_at"],
}


@app.on_event("startup")
def on_startup() -> None:
    init_db()



def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    ensure_schema_compatibility()
    normalize_datetime_storage()


def ensure_schema_compatibility() -> None:
    if not DB_PATH.exists():
        return

    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(tasks)")
        task_columns = {row[1] for row in cur.fetchall()}
        if "completion_note" not in task_columns:
            cur.execute("ALTER TABLE tasks ADD COLUMN completion_note TEXT")
            conn.commit()

        cur.execute("PRAGMA table_info(board_preferences)")
        board_preference_columns = {row[1] for row in cur.fetchall()}
        if board_preference_columns and "project_order_json" not in board_preference_columns:
            cur.execute("ALTER TABLE board_preferences ADD COLUMN project_order_json TEXT NOT NULL DEFAULT '[]'")
            conn.commit()
    finally:
        conn.close()


def normalize_datetime_storage() -> None:
    if not DB_PATH.exists():
        return

    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        for table, columns in DATETIME_COLUMNS.items():
            for column in columns:
                cur.execute(f"SELECT rowid, {column} FROM {table} WHERE {column} IS NOT NULL")
                updates: list[tuple[str, int]] = []
                for rowid, raw_value in cur.fetchall():
                    if raw_value is None:
                        continue
                    normalized = to_storage_string(raw_value)
                    if normalized and normalized != raw_value:
                        updates.append((normalized, rowid))
                if updates:
                    cur.executemany(f"UPDATE {table} SET {column}=? WHERE rowid=?", updates)
        conn.commit()
    finally:
        conn.close()



def get_board_preference(db: Session) -> BoardPreference:
    preference = db.scalar(select(BoardPreference).limit(1))
    if preference is None:
        preference = BoardPreference()
        db.add(preference)
        db.flush()
    return preference


def serialize_board_preference(preference: BoardPreference) -> BoardPreferenceRead:
    try:
        task_order = [int(item) for item in json.loads(preference.task_order_json or "[]") if int(item) > 0]
    except Exception:
        task_order = []

    try:
        pinned_projects = [str(item).strip() for item in json.loads(preference.pinned_projects_json or "[]") if str(item).strip()]
    except Exception:
        pinned_projects = []

    try:
        project_order = [str(item).strip() for item in json.loads(preference.project_order_json or "[]") if str(item).strip()]
    except Exception:
        project_order = []

    normalized_projects: list[str] = []
    for project in pinned_projects:
        if project not in normalized_projects:
            normalized_projects.append(project)

    normalized_project_order: list[str] = []
    for project in project_order:
        if project not in normalized_project_order:
            normalized_project_order.append(project)

    return BoardPreferenceRead(task_order=task_order, pinned_projects=normalized_projects, project_order=normalized_project_order)


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
        completion_note=task.completion_note,
        canceled_at=task.canceled_at,
        deferred_to=task.deferred_to,
        nightly_bucket=task.nightly_bucket,
        nightly_reviewed_at=task.nightly_reviewed_at,
        reminders=[ReminderRead.model_validate(reminder) for reminder in sorted(task.reminders, key=lambda r: r.remind_at)],
        recurrence=serialize_recurrence(task.recurrence),
    )


def parse_json_object(raw_value: str | None) -> dict[str, Any]:
    if not raw_value:
        return {}
    try:
        value = json.loads(raw_value)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def parse_json_list(raw_value: str | None) -> list[str]:
    if not raw_value:
        return []
    try:
        value = json.loads(raw_value)
    except json.JSONDecodeError:
        return []
    if not isinstance(value, list):
        return []
    normalized: list[str] = []
    for item in value:
        text = str(item).strip()
        if text and text not in normalized:
            normalized.append(text)
    return normalized


def serialize_customer_material(material: CustomerMaterial) -> CustomerMaterialRead:
    return CustomerMaterialRead(
        id=material.id,
        project=material.project,
        title=material.title,
        material_date=material.material_date,
        source_type=material.source_type,
        source=material.source,
        source_refs=parse_json_object(material.source_refs_json),
        raw_source_markdown=material.raw_source_markdown,
        candidate_markdown=material.candidate_markdown,
        value_types=parse_json_list(material.value_types_json),
        status=material.status,
        review_note=material.review_note,
        task_id=material.task_id,
        created_at=material.created_at,
        updated_at=material.updated_at,
        archived_at=material.archived_at,
    )


def get_customer_material_or_404(db: Session, material_id: int) -> CustomerMaterial:
    material = db.scalar(select(CustomerMaterial).where(CustomerMaterial.id == material_id))
    if not material:
        raise HTTPException(status_code=404, detail="Customer material not found")
    return material


def validate_task_reference(db: Session, task_id: int | None) -> None:
    if task_id is None:
        return
    if not db.get(Task, task_id):
        raise HTTPException(status_code=404, detail="Referenced task not found")


def validate_customer_material_status(status: str | None) -> None:
    if status is None:
        return
    if status not in {item.value for item in CustomerMaterialStatus}:
        raise HTTPException(status_code=400, detail="Invalid customer material status")



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



def today_local() -> date:
    return now_local().date()



def task_schedule_at(task: Task) -> datetime | None:
    return task.deferred_to or task.due_at



def get_board_sort_metadata(db: Session) -> tuple[dict[int, int], list[str], list[str]]:
    preference = serialize_board_preference(get_board_preference(db))
    task_order_map = {task_id: index for index, task_id in enumerate(preference.task_order)}
    return task_order_map, preference.pinned_projects, preference.project_order



def sort_tasks_for_board(tasks: list[Task], task_order_map: dict[int, int]) -> list[Task]:
    def sort_key(task: Task) -> tuple[int, int, datetime, datetime]:
        custom_rank = task_order_map.get(task.id, 10**9)
        schedule_at = task_schedule_at(task) or datetime.max.replace(tzinfo=UTC)
        return (0 if task.id in task_order_map else 1, custom_rank, schedule_at, task.updated_at)

    return sorted(tasks, key=sort_key)



def recurrence_anchor(task: Task, payload: TaskRecurrenceWrite | None = None) -> datetime:
    return (
        (payload.start_at if payload else None)
        or task.due_at
        or (task.recurrence.next_run_at if task.recurrence and task.recurrence.next_run_at else None)
        or now_utc().replace(microsecond=0)
    )



def compute_recurrence_next_run(task: Task, recurrence: TaskRecurrence, *, after_dt: datetime | None = None) -> datetime | None:
    anchor = recurrence.start_at or task.due_at or recurrence.next_run_at or now_utc().replace(microsecond=0)
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
        timezone_name=recurrence.timezone,
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
        after_dt=now_utc().replace(microsecond=0),
        time_of_day=payload.time_of_day,
        days_of_week=payload.days_of_week,
        day_of_month=payload.day_of_month,
        start_at=payload.start_at,
        end_at=payload.end_at,
        timezone_name=payload.timezone,
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



def build_plan_groups(db: Session, target: date | None = None) -> list[PlanGroup]:
    target = target or today_local()
    _, future_start = local_day_bounds(target)
    not_started_statuses = [TaskStatus.TODO.value, TaskStatus.DEFERRED.value]
    schedule_at = func.coalesce(Task.deferred_to, Task.due_at)
    tasks = list(
        db.scalars(
            select(Task)
            .where(Task.status.in_(not_started_statuses), schedule_at >= future_start)
            .options(*task_load_options())
            .order_by(schedule_at.asc(), Task.created_at.asc())
        ).unique()
    )

    grouped: dict[date, list[Task]] = {}
    for task in tasks:
        schedule_value = task_schedule_at(task)
        group_date = local_date(schedule_value)
        if group_date is None:
            continue
        grouped.setdefault(group_date, []).append(task)

    sorted_dates = sorted(grouped.keys())

    plan_groups: list[PlanGroup] = []
    for group_date in sorted_dates:
        group_tasks = sorted(
            grouped[group_date],
            key=lambda task: (task_schedule_at(task) or datetime.max.replace(tzinfo=UTC), task.created_at),
        )
        plan_groups.append(
            PlanGroup(
                key=group_date.isoformat(),
                title=group_date.isoformat(),
                group_date=group_date,
                tasks=[serialize_task(task) for task in group_tasks],
            )
        )

    return plan_groups



def build_plan_summary(db: Session, target: date | None = None) -> PlanSummary:
    target = target or today_local()
    plan_groups = build_plan_groups(db, target)
    total = sum(len(group.tasks) for group in plan_groups)
    return PlanSummary(
        date=target,
        total=total,
        open_count=total,
        plan_groups=plan_groups,
    )



def build_today_summary(db: Session, target: date | None = None) -> TodaySummary:
    target = target or today_local()
    start, end = local_day_bounds(target)
    open_statuses = {TaskStatus.TODO.value, TaskStatus.DOING.value, TaskStatus.DEFERRED.value}
    schedule_at = func.coalesce(Task.deferred_to, Task.due_at)
    stmt = (
        select(Task)
        .where(
            or_(
                Task.due_at.between(start, end - timedelta(microseconds=1)),
                Task.deferred_to.between(start, end - timedelta(microseconds=1)),
                and_(Task.status.in_(list(open_statuses)), schedule_at < start),
            )
        )
        .options(*task_load_options())
        .order_by(schedule_at.is_(None), schedule_at.asc(), Task.created_at.asc())
    )
    tasks = list(db.scalars(stmt).unique())
    items = [serialize_task(task) for task in tasks]
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
    task_order_map, _, _ = get_board_sort_metadata(db)
    grouped: list[TaskBoardGroup] = []
    for status in status_order:
        status_tasks = [task for task in tasks if task.status == status]
        grouped.append(TaskBoardGroup(status=status, tasks=[serialize_task(task) for task in sort_tasks_for_board(status_tasks, task_order_map)]))
    return BoardSummary(groups=grouped)



def build_history_summary(db: Session, *, target: date | None = None, status: str | None = None, query: str | None = None) -> HistorySummary:
    stmt = query_tasks(db, status=status, query=query)
    if target:
        start, end = local_day_bounds(target)
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
    _, pinned_projects, project_order = get_board_sort_metadata(db)
    pinned_index = {name: index for index, name in enumerate(pinned_projects)}
    project_order_index = {name: index for index, name in enumerate(project_order)}

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
        key=lambda item: (
            0 if item.name in pinned_index else 1,
            pinned_index.get(item.name, 10**9),
            0 if item.name in project_order_index else 1,
            project_order_index.get(item.name, 10**9),
            -item.open_task_count,
            -item.task_count,
            item.name,
        ),
    )


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", db=str(DB_PATH), now=now_local())


@app.get("/api/tasks", response_model=list[TaskRead])
def list_tasks(
    status: str | None = Query(default=None),
    date_filter: str | None = Query(default=None, alias="date"),
    q: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[TaskRead]:
    stmt = query_tasks(db, status=status, query=q)
    if date_filter == "today":
        start, end = local_day_bounds(today_local())
        stmt = stmt.where(Task.due_at.between(start, end - timedelta(microseconds=1)))
    tasks = list(db.scalars(stmt).unique())
    return [serialize_task(task) for task in tasks]


@app.get("/api/projects", response_model=list[ProjectSummary])
def list_projects(db: Session = Depends(get_db)) -> list[ProjectSummary]:
    return build_project_summaries(db)


@app.get("/api/preferences/board", response_model=BoardPreferenceRead)
def get_board_preferences(db: Session = Depends(get_db)) -> BoardPreferenceRead:
    return serialize_board_preference(get_board_preference(db))


@app.patch("/api/preferences/board", response_model=BoardPreferenceRead)
def update_board_preferences(payload: BoardPreferenceUpdate, db: Session = Depends(get_db)) -> BoardPreferenceRead:
    preference = get_board_preference(db)
    updates = payload.model_dump(exclude_unset=True)

    if "task_order" in updates and updates["task_order"] is not None:
        preference.task_order_json = json.dumps(updates["task_order"], ensure_ascii=False)
    if "pinned_projects" in updates and updates["pinned_projects"] is not None:
        preference.pinned_projects_json = json.dumps(updates["pinned_projects"], ensure_ascii=False)
    if "project_order" in updates and updates["project_order"] is not None:
        preference.project_order_json = json.dumps(updates["project_order"], ensure_ascii=False)

    db.add(preference)
    db.commit()
    db.refresh(preference)
    return serialize_board_preference(preference)


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

    preference = get_board_preference(db)
    serialized_preference = serialize_board_preference(preference)
    pinned_projects = serialized_preference.pinned_projects
    project_order = serialized_preference.project_order
    if payload.old_name in pinned_projects:
        pinned_projects = [payload.new_name if name == payload.old_name else name for name in pinned_projects]
        preference.pinned_projects_json = json.dumps(pinned_projects, ensure_ascii=False)
        db.add(preference)
    if payload.old_name in project_order:
        project_order = [payload.new_name if name == payload.old_name else name for name in project_order]
        preference.project_order_json = json.dumps(project_order, ensure_ascii=False)
        db.add(preference)

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


@app.get("/api/customer-materials", response_model=list[CustomerMaterialRead])
def list_customer_materials(
    project: str | None = Query(default=None),
    q: str | None = Query(default=None),
    status: str | None = Query(default=None),
    value_type: str | None = Query(default=None),
    task_id: int | None = Query(default=None),
    include_archived: bool = False,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[CustomerMaterialRead]:
    validate_customer_material_status(status)
    stmt = select(CustomerMaterial)
    if project:
        normalized_project = normalize_project_name(project)
        if normalized_project:
            stmt = stmt.where(CustomerMaterial.project == normalized_project)
    if status:
        stmt = stmt.where(CustomerMaterial.status == status)
    if task_id is not None:
        stmt = stmt.where(CustomerMaterial.task_id == task_id)
    if not include_archived:
        stmt = stmt.where(CustomerMaterial.archived_at.is_(None))
    if value_type:
        # value_types are stored as a JSON array; LIKE is enough for MVP filtering.
        stmt = stmt.where(CustomerMaterial.value_types_json.like(f"%{value_type.strip()}%"))
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                CustomerMaterial.title.like(pattern),
                CustomerMaterial.project.like(pattern),
                CustomerMaterial.raw_source_markdown.like(pattern),
                CustomerMaterial.candidate_markdown.like(pattern),
            )
        )
    stmt = stmt.order_by(CustomerMaterial.updated_at.desc(), CustomerMaterial.id.desc()).limit(limit)
    return [serialize_customer_material(material) for material in db.scalars(stmt).all()]


@app.post("/api/customer-materials", response_model=CustomerMaterialRead, status_code=201)
def create_customer_material(payload: CustomerMaterialCreate, db: Session = Depends(get_db)) -> CustomerMaterialRead:
    validate_task_reference(db, payload.task_id)
    validate_customer_material_status(payload.status)
    material = CustomerMaterial(
        project=payload.project,
        title=payload.title,
        material_date=payload.material_date,
        source_type=payload.source_type,
        source=payload.source,
        source_refs_json=json.dumps(payload.source_refs, ensure_ascii=False),
        raw_source_markdown=payload.raw_source_markdown,
        candidate_markdown=payload.candidate_markdown,
        value_types_json=json.dumps(payload.value_types, ensure_ascii=False),
        status=payload.status,
        review_note=payload.review_note,
        task_id=payload.task_id,
    )
    db.add(material)
    db.commit()
    db.refresh(material)
    return serialize_customer_material(material)


@app.get("/api/customer-materials/{material_id}", response_model=CustomerMaterialRead)
def get_customer_material(material_id: int, db: Session = Depends(get_db)) -> CustomerMaterialRead:
    return serialize_customer_material(get_customer_material_or_404(db, material_id))


@app.patch("/api/customer-materials/{material_id}", response_model=CustomerMaterialRead)
def update_customer_material(material_id: int, payload: CustomerMaterialUpdate, db: Session = Depends(get_db)) -> CustomerMaterialRead:
    material = get_customer_material_or_404(db, material_id)
    updates = payload.model_dump(exclude_unset=True)
    clear_task = bool(updates.pop("clear_task", False))
    if "status" in updates:
        validate_customer_material_status(updates["status"])
    if "task_id" in updates:
        validate_task_reference(db, updates["task_id"])
    if clear_task:
        material.task_id = None
    if "source_refs" in updates:
        material.source_refs_json = json.dumps(updates.pop("source_refs") or {}, ensure_ascii=False)
    if "value_types" in updates:
        material.value_types_json = json.dumps(updates.pop("value_types") or [], ensure_ascii=False)
    for field, value in updates.items():
        setattr(material, field, value)
    db.add(material)
    db.commit()
    db.refresh(material)
    return serialize_customer_material(material)


@app.delete("/api/customer-materials/{material_id}", response_model=CustomerMaterialRead)
def archive_customer_material(material_id: int, db: Session = Depends(get_db)) -> CustomerMaterialRead:
    material = get_customer_material_or_404(db, material_id)
    if material.archived_at is None:
        material.archived_at = now_utc()
        db.add(material)
        db.commit()
        db.refresh(material)
    return serialize_customer_material(material)


@app.get("/api/tasks/{task_id}/customer-materials", response_model=list[CustomerMaterialRead])
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
    add_event(db, task, EventType.UPDATED.value, {"before": before, "after": payload.model_dump(mode="json", exclude_unset=True)})
    db.commit()
    task = get_task_or_404(db, task_id)
    detail = serialize_task(task)
    return TaskDetail(**detail.model_dump(), events=[serialize_event(event) for event in sorted(task.events, key=lambda e: e.created_at, reverse=True)])


@app.post("/api/tasks/{task_id}/complete", response_model=TaskDetail)
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
    task.completion_note = None
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
    canceled_at = payload.canceled_at or now_utc()
    task.status = TaskStatus.CANCELED.value
    task.canceled_at = canceled_at
    task.completed_at = None
    task.completion_note = None
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


@app.get("/api/dashboard/plan", response_model=PlanSummary)
def dashboard_plan(db: Session = Depends(get_db)) -> PlanSummary:
    return build_plan_summary(db)


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
