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
from models import BoardPreference, Customer, CustomerMaterial, CustomerMaterialFact, CustomerMaterialStatus, CustomerStatus, EventType, Fact, FactStatus, MaterialType, Project as ProjectV2, ProjectStatus, ProjectType, Reminder, ReminderStatus, ReviewBatch, ReviewBatchStatus, ReviewBatchType, Task, TaskEvent, TaskRecurrence, TaskStatus
from recurrence import compute_next_recurrence, normalize_days_of_week, normalize_time_of_day
from timeutils import APP_TIMEZONE, UTC, local_date, local_day_bounds, now_local, now_utc, parse_datetime_string, to_storage_string
from schemas import (
    BoardPreferenceRead,
    BoardPreferenceUpdate,
    BoardSummary,
    CustomerCreate,
    CustomerMaterialCreate,
    CustomerMaterialFactCreate,
    CustomerMaterialFactRead,
    CustomerMaterialRead,
    CustomerMaterialUpdate,
    CustomerMaterialV2Create,
    CustomerMaterialV2Read,
    CustomerMaterialV2Update,
    CustomerRead,
    CustomerUpdate,
    DashboardPayload,
    FactCreate,
    FactRead,
    FactUpdate,
    HealthResponse,
    HistorySummary,
    NightlyReviewPlaceholder,
    PlanGroup,
    PlanSummary,
    ProjectRenameRequest,
    ProjectRenameResponse,
    ProjectSummary,
    ProjectV2Create,
    ProjectV2Read,
    ProjectV2Update,
    ReminderCreate,
    ReminderRead,
    ReviewBatchCreate,
    ReviewBatchRead,
    ReviewBatchUpdate,
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
    "customer_materials": ["material_date", "created_at", "updated_at", "archived_at", "period_start", "period_end"],
    "customers": ["created_at", "updated_at"],
    "projects": ["start_at", "target_end_at", "actual_end_at", "created_at", "updated_at"],
    "facts": ["fact_date", "created_at", "updated_at"],
    "review_batches": ["period_start", "period_end", "created_at", "updated_at"],
    "customer_material_facts": ["created_at"],
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

        # --- tasks: add v2 columns ---
        cur.execute("PRAGMA table_info(tasks)")
        task_columns = {row[1] for row in cur.fetchall()}
        if "completion_note" not in task_columns:
            cur.execute("ALTER TABLE tasks ADD COLUMN completion_note TEXT")
        if "area" not in task_columns:
            cur.execute("ALTER TABLE tasks ADD COLUMN area VARCHAR(128)")
        if "customer_id" not in task_columns:
            cur.execute("ALTER TABLE tasks ADD COLUMN customer_id INTEGER REFERENCES customers(id) ON DELETE SET NULL")
        if "project_id" not in task_columns:
            cur.execute("ALTER TABLE tasks ADD COLUMN project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL")
        if "source_type" not in task_columns:
            cur.execute("ALTER TABLE tasks ADD COLUMN source_type VARCHAR(32)")

        # --- board_preferences ---
        cur.execute("PRAGMA table_info(board_preference)")
        board_preference_columns = {row[1] for row in cur.fetchall()}
        if board_preference_columns and "project_order_json" not in board_preference_columns:
            cur.execute("ALTER TABLE board_preferences ADD COLUMN project_order_json TEXT NOT NULL DEFAULT '[]'")

        # --- customer_materials: add v2 columns ---
        cur.execute("PRAGMA table_info(customer_materials)")
        cm_columns = {row[1] for row in cur.fetchall()}
        v2_cm_cols = {
            "customer_id": "INTEGER REFERENCES customers(id) ON DELETE SET NULL",
            "project_v2_id": "INTEGER REFERENCES projects(id) ON DELETE SET NULL",
            "review_batch_id": "INTEGER REFERENCES review_batches(id) ON DELETE SET NULL",
            "material_type": "VARCHAR(32) DEFAULT 'period_summary'",
            "period_start": "TEXT",
            "period_end": "TEXT",
            "raw_facts_markdown": "TEXT",
            "summary_markdown": "TEXT",
            "insights_markdown": "TEXT",
            "generation_meta_json": "TEXT",
        }
        for col_name, col_def in v2_cm_cols.items():
            if col_name not in cm_columns:
                cur.execute(f"ALTER TABLE customer_materials ADD COLUMN {col_name} {col_def}")

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
        area=getattr(task, 'area', None),
        customer_id=getattr(task, 'customer_id', None),
        project_id=getattr(task, 'project_id', None),
        tags=json.loads(task.tags_json or "[]"),
        source=task.source,
        source_type=getattr(task, 'source_type', None),
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
        # V2 fields
        customer_id=getattr(material, 'customer_id', None),
        project_v2_id=getattr(material, 'project_v2_id', None),
        review_batch_id=getattr(material, 'review_batch_id', None),
        material_type=getattr(material, 'material_type', None),
        period_start=getattr(material, 'period_start', None),
        period_end=getattr(material, 'period_end', None),
        raw_facts_markdown=getattr(material, 'raw_facts_markdown', None),
        summary_markdown=getattr(material, 'summary_markdown', None),
        insights_markdown=getattr(material, 'insights_markdown', None),
        generation_meta=parse_json_object(getattr(material, 'generation_meta_json', None)),
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


def validate_customer_material_references(
    db: Session,
    *,
    customer_id: int | None = None,
    project_v2_id: int | None = None,
    review_batch_id: int | None = None,
) -> Customer | None:
    customer = None
    if customer_id is not None:
        customer = db.get(Customer, customer_id)
        if not customer:
            raise HTTPException(status_code=404, detail="Referenced customer not found")
    if project_v2_id is not None and not db.get(ProjectV2, project_v2_id):
        raise HTTPException(status_code=404, detail="Referenced project not found")
    if review_batch_id is not None and not db.get(ReviewBatch, review_batch_id):
        raise HTTPException(status_code=404, detail="Referenced review batch not found")
    return customer


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



def query_tasks(
    db: Session,
    *,
    status: str | None = None,
    query: str | None = None,
    source_type: str | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
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
    source_type: str | None = Query(default=None),
    created_from: datetime | None = Query(default=None, alias="from"),
    created_to: datetime | None = Query(default=None, alias="to"),
    db: Session = Depends(get_db),
) -> list[TaskRead]:
    stmt = query_tasks(
        db,
        status=status,
        query=q,
        source_type=source_type,
        created_from=created_from,
        created_to=created_to,
    )
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
    # V2 query params per API consolidation plan
    customer_id: int | None = Query(default=None),
    project_v2_id: int | None = Query(default=None),
    review_batch_id: int | None = Query(default=None),
    material_type: str | None = Query(default=None),
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
    if customer_id is not None:
        stmt = stmt.where(CustomerMaterial.customer_id == customer_id)
    if project_v2_id is not None:
        stmt = stmt.where(CustomerMaterial.project_v2_id == project_v2_id)
    if review_batch_id is not None:
        stmt = stmt.where(CustomerMaterial.review_batch_id == review_batch_id)
    if material_type:
        stmt = stmt.where(CustomerMaterial.material_type == material_type)
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
    customer = validate_customer_material_references(
        db,
        customer_id=payload.customer_id,
        project_v2_id=payload.project_v2_id,
        review_batch_id=payload.review_batch_id,
    )
    # Auto-fill legacy project from customer info if v2 fields are primary
    project_str = payload.project
    if project_str is None and customer is not None:
        project_str = customer.area or customer.name
    material = CustomerMaterial(
        project=project_str or "",
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
        # V2 fields
        customer_id=payload.customer_id,
        project_v2_id=payload.project_v2_id,
        review_batch_id=payload.review_batch_id,
        material_type=payload.material_type,
        period_start=payload.period_start,
        period_end=payload.period_end,
        raw_facts_markdown=payload.raw_facts_markdown,
        summary_markdown=payload.summary_markdown,
        insights_markdown=payload.insights_markdown,
        generation_meta_json=json.dumps(payload.generation_meta, ensure_ascii=False) if payload.generation_meta else None,
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
    clear_project_v2 = bool(updates.pop("clear_project_v2", False))
    clear_batch = bool(updates.pop("clear_batch", False))
    if "status" in updates:
        validate_customer_material_status(updates["status"])
    if "task_id" in updates:
        validate_task_reference(db, updates["task_id"])
    validate_customer_material_references(
        db,
        customer_id=updates.get("customer_id") if "customer_id" in updates else None,
        project_v2_id=updates.get("project_v2_id") if "project_v2_id" in updates else None,
        review_batch_id=updates.get("review_batch_id") if "review_batch_id" in updates else None,
    )
    if clear_task:
        material.task_id = None
    if clear_project_v2:
        setattr(material, 'project_v2_id', None)
    if clear_batch:
        setattr(material, 'review_batch_id', None)
    if "source_refs" in updates:
        material.source_refs_json = json.dumps(updates.pop("source_refs") or {}, ensure_ascii=False)
    if "value_types" in updates:
        material.value_types_json = json.dumps(updates.pop("value_types") or [], ensure_ascii=False)
    if "generation_meta" in updates:
        meta = updates.pop("generation_meta")
        setattr(material, 'generation_meta_json', json.dumps(meta, ensure_ascii=False) if meta else None)
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


@app.post("/api/customer-materials/{material_id}/mark-uploaded", response_model=CustomerMaterialRead)
def mark_material_uploaded_main(material_id: int, db: Session = Depends(get_db)) -> CustomerMaterialRead:
    """Mark a customer material as uploaded (consolidated into main path)."""
    material = get_customer_material_or_404(db, material_id)
    material.status = CustomerMaterialStatus.UPLOADED.value
    db.add(material)
    db.commit()
    db.refresh(material)
    return serialize_customer_material(material)


@app.post("/api/customer-materials/{material_id}/facts", response_model=CustomerMaterialFactRead, status_code=201)
def add_material_fact_main(material_id: int, payload: CustomerMaterialFactCreate, db: Session = Depends(get_db)) -> CustomerMaterialFactRead:
    """Add a fact to a customer material (consolidated into main path)."""
    material = get_customer_material_or_404(db, material_id)
    fact = db.get(Fact, payload.fact_id)
    if not fact:
        raise HTTPException(status_code=404, detail="Fact not found")
    mf = CustomerMaterialFact(
        material_id=material.id,
        fact_id=payload.fact_id,
        sort_order=payload.sort_order,
    )
    db.add(mf)
    db.commit()
    db.refresh(mf)
    return serialize_material_fact(mf)


@app.get("/api/customer-materials/{material_id}/facts", response_model=list[CustomerMaterialFactRead])
def list_material_facts_main(material_id: int, db: Session = Depends(get_db)) -> list[CustomerMaterialFactRead]:
    """List facts associated with a customer material (consolidated into main path)."""
    get_customer_material_or_404(db, material_id)
    stmt = select(CustomerMaterialFact).where(
        CustomerMaterialFact.material_id == material_id
    ).order_by(CustomerMaterialFact.sort_order.asc())
    return [serialize_material_fact(mf) for mf in db.scalars(stmt).all()]


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
        area=getattr(payload, 'area', None),
        customer_id=getattr(payload, 'customer_id', None),
        project_id=getattr(payload, 'project_id', None),
        tags_json=json.dumps(payload.tags, ensure_ascii=False),
        source=payload.source,
        source_type=getattr(payload, 'source_type', None),
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
    updates.pop("clear_customer", None)
    updates.pop("clear_project_v2", None)
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


# ════════════════════════════════════════════════════════════════════
# V2 API: Customers / Projects / Facts / ReviewBatches / MaterialFacts
# ════════════════════════════════════════════════════════════════════


def serialize_customer(customer: Customer) -> CustomerRead:
    return CustomerRead(
        id=customer.id,
        name=customer.name,
        key=customer.key,
        aliases=parse_json_list(customer.aliases_json),
        status=customer.status,
        description=customer.description,
        area=customer.area,
        tags=parse_json_list(customer.tags_json),
        created_at=customer.created_at,
        updated_at=customer.updated_at,
    )


def serialize_project_v2(project: ProjectV2) -> ProjectV2Read:
    return ProjectV2Read(
        id=project.id,
        customer_id=project.customer_id,
        project_type=project.project_type,
        name=project.name,
        status=project.status,
        area=project.area,
        tags=parse_json_list(project.tags_json),
        start_at=project.start_at,
        target_end_at=project.target_end_at,
        actual_end_at=project.actual_end_at,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


def serialize_fact(fact: Fact) -> FactRead:
    return FactRead(
        id=fact.id,
        customer_id=fact.customer_id,
        project_id=fact.project_id,
        task_id=fact.task_id,
        fact_date=fact.fact_date,
        title=fact.title,
        raw_markdown=fact.raw_markdown,
        source_type=fact.source_type,
        value_types=parse_json_list(fact.value_types_json),
        status=fact.status,
        created_at=fact.created_at,
        updated_at=fact.updated_at,
    )


def serialize_review_batch(batch: ReviewBatch) -> ReviewBatchRead:
    return ReviewBatchRead(
        id=batch.id,
        batch_type=batch.batch_type,
        title=batch.title,
        period_start=batch.period_start,
        period_end=batch.period_end,
        status=batch.status,
        material_count=batch.material_count,
        created_by=batch.created_by,
        created_at=batch.created_at,
        updated_at=batch.updated_at,
    )


def serialize_material_v2(material: CustomerMaterial) -> CustomerMaterialV2Read:
    return CustomerMaterialV2Read(
        id=material.id,
        customer_id=getattr(material, 'customer_id', None),
        project_v2_id=getattr(material, 'project_v2_id', None),
        review_batch_id=getattr(material, 'review_batch_id', None),
        title=material.title,
        material_type=getattr(material, 'material_type', 'period_summary'),
        period_start=getattr(material, 'period_start', None),
        period_end=getattr(material, 'period_end', None),
        raw_facts_markdown=getattr(material, 'raw_facts_markdown', None),
        summary_markdown=getattr(material, 'summary_markdown', None),
        insights_markdown=getattr(material, 'insights_markdown', None),
        status=material.status,
        generation_meta=parse_json_object(getattr(material, 'generation_meta_json', None)),
        project=material.project,
        created_at=material.created_at,
        updated_at=material.updated_at,
    )


def serialize_material_fact(mf: CustomerMaterialFact) -> CustomerMaterialFactRead:
    return CustomerMaterialFactRead(
        id=mf.id,
        material_id=mf.material_id,
        fact_id=mf.fact_id,
        sort_order=mf.sort_order,
        created_at=mf.created_at,
    )


# --- Customers ---

@app.get("/api/customers", response_model=list[CustomerRead])
def list_customers(
    q: str | None = Query(default=None),
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[CustomerRead]:
    stmt = select(Customer)
    if status:
        stmt = stmt.where(Customer.status == status)
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Customer.name.ilike(pattern),
                Customer.key.ilike(pattern),
                Customer.area.ilike(pattern),
                Customer.aliases_json.like(pattern),
            )
        )
    stmt = stmt.order_by(Customer.name.asc())
    return [serialize_customer(c) for c in db.scalars(stmt).all()]


@app.post("/api/customers", response_model=CustomerRead, status_code=201)
def create_customer(payload: CustomerCreate, db: Session = Depends(get_db)) -> CustomerRead:
    area = payload.area or f"\u5ba2\u6237_{payload.name}"
    aliases = list(payload.aliases)
    if area not in aliases:
        aliases.append(area)
    customer = Customer(
        name=payload.name,
        key=payload.key,
        aliases_json=json.dumps(aliases, ensure_ascii=False),
        status=payload.status,
        description=payload.description,
        area=area,
        tags_json=json.dumps(payload.tags, ensure_ascii=False),
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return serialize_customer(customer)


@app.get("/api/customers/{customer_id}", response_model=CustomerRead)
def get_customer(customer_id: int, db: Session = Depends(get_db)) -> CustomerRead:
    customer = db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return serialize_customer(customer)


@app.patch("/api/customers/{customer_id}", response_model=CustomerRead)
def update_customer(customer_id: int, payload: CustomerUpdate, db: Session = Depends(get_db)) -> CustomerRead:
    customer = db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    updates = payload.model_dump(exclude_unset=True)
    if "aliases" in updates:
        customer.aliases_json = json.dumps(updates.pop("aliases"), ensure_ascii=False)
    if "tags" in updates:
        customer.tags_json = json.dumps(updates.pop("tags"), ensure_ascii=False)
    for field, value in updates.items():
        setattr(customer, field, value)
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return serialize_customer(customer)


# --- Projects V2 ---

@app.get("/api/projects-v2", response_model=list[ProjectV2Read])
def list_projects_v2(
    customer_id: int | None = Query(default=None),
    area: str | None = Query(default=None),
    status: str | None = Query(default=None),
    q: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[ProjectV2Read]:
    stmt = select(ProjectV2)
    if customer_id is not None:
        stmt = stmt.where(ProjectV2.customer_id == customer_id)
    if area:
        normalized = normalize_project_name(area)
        if normalized:
            stmt = stmt.where(ProjectV2.area == normalized)
    if status:
        stmt = stmt.where(ProjectV2.status == status)
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(ProjectV2.name.ilike(pattern))
    stmt = stmt.order_by(ProjectV2.created_at.desc())
    return [serialize_project_v2(p) for p in db.scalars(stmt).all()]


@app.post("/api/projects-v2", response_model=ProjectV2Read, status_code=201)
def create_project_v2(payload: ProjectV2Create, db: Session = Depends(get_db)) -> ProjectV2Read:
    area = payload.area
    if area is None and payload.customer_id is not None:
        customer = db.get(Customer, payload.customer_id)
        if customer and customer.area:
            area = customer.area
    project = ProjectV2(
        customer_id=payload.customer_id,
        project_type=payload.project_type,
        name=payload.name,
        status=payload.status,
        area=area,
        tags_json=json.dumps(payload.tags, ensure_ascii=False),
        start_at=payload.start_at,
        target_end_at=payload.target_end_at,
        actual_end_at=payload.actual_end_at,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return serialize_project_v2(project)


@app.get("/api/projects-v2/{project_id}", response_model=ProjectV2Read)
def get_project_v2(project_id: int, db: Session = Depends(get_db)) -> ProjectV2Read:
    project = db.get(ProjectV2, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return serialize_project_v2(project)


@app.patch("/api/projects-v2/{project_id}", response_model=ProjectV2Read)
def update_project_v2(project_id: int, payload: ProjectV2Update, db: Session = Depends(get_db)) -> ProjectV2Read:
    project = db.get(ProjectV2, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    updates = payload.model_dump(exclude_unset=True)
    clear_customer = bool(updates.pop("clear_customer", False))
    if "tags" in updates:
        project.tags_json = json.dumps(updates.pop("tags"), ensure_ascii=False)
    for field, value in updates.items():
        setattr(project, field, value)
    if clear_customer:
        project.customer_id = None
    db.add(project)
    db.commit()
    db.refresh(project)
    return serialize_project_v2(project)


# --- Facts ---

@app.get("/api/facts", response_model=list[FactRead])
def list_facts(
    customer_id: int | None = Query(default=None),
    project_id: int | None = Query(default=None),
    task_id: int | None = Query(default=None),
    status: str | None = Query(default=None),
    source_type: str | None = Query(default=None),
    from_date: datetime | None = Query(default=None, alias="from"),
    to_date: datetime | None = Query(default=None, alias="to"),
    q: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[FactRead]:
    stmt = select(Fact)
    if customer_id is not None:
        stmt = stmt.where(Fact.customer_id == customer_id)
    if project_id is not None:
        stmt = stmt.where(Fact.project_id == project_id)
    if task_id is not None:
        stmt = stmt.where(Fact.task_id == task_id)
    if status:
        stmt = stmt.where(Fact.status == status)
    if source_type:
        stmt = stmt.where(Fact.source_type == source_type)
    if from_date:
        stmt = stmt.where(Fact.fact_date >= from_date)
    if to_date:
        stmt = stmt.where(Fact.fact_date < to_date)
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Fact.title.ilike(pattern),
                Fact.raw_markdown.ilike(pattern),
            )
        )
    stmt = stmt.order_by(Fact.fact_date.desc(), Fact.id.desc()).limit(limit)
    return [serialize_fact(f) for f in db.scalars(stmt).all()]


@app.post("/api/facts", response_model=FactRead, status_code=201)
def create_fact(payload: FactCreate, db: Session = Depends(get_db)) -> FactRead:
    fact = Fact(
        customer_id=payload.customer_id,
        project_id=payload.project_id,
        task_id=payload.task_id,
        fact_date=payload.fact_date,
        title=payload.title,
        raw_markdown=payload.raw_markdown,
        source_type=payload.source_type,
        value_types_json=json.dumps(payload.value_types, ensure_ascii=False),
        status=payload.status,
    )
    db.add(fact)
    db.commit()
    db.refresh(fact)
    return serialize_fact(fact)


@app.get("/api/facts/{fact_id}", response_model=FactRead)
def get_fact(fact_id: int, db: Session = Depends(get_db)) -> FactRead:
    fact = db.get(Fact, fact_id)
    if not fact:
        raise HTTPException(status_code=404, detail="Fact not found")
    return serialize_fact(fact)


@app.patch("/api/facts/{fact_id}", response_model=FactRead)
def update_fact(fact_id: int, payload: FactUpdate, db: Session = Depends(get_db)) -> FactRead:
    fact = db.get(Fact, fact_id)
    if not fact:
        raise HTTPException(status_code=404, detail="Fact not found")
    updates = payload.model_dump(exclude_unset=True)
    clear_customer = bool(updates.pop("clear_customer", False))
    clear_project = bool(updates.pop("clear_project", False))
    clear_task = bool(updates.pop("clear_task", False))
    if "value_types" in updates:
        fact.value_types_json = json.dumps(updates.pop("value_types"), ensure_ascii=False)
    for field, value in updates.items():
        setattr(fact, field, value)
    if clear_customer:
        fact.customer_id = None
    if clear_project:
        fact.project_id = None
    if clear_task:
        fact.task_id = None
    db.add(fact)
    db.commit()
    db.refresh(fact)
    return serialize_fact(fact)


@app.delete("/api/facts/{fact_id}", response_model=FactRead)
def delete_fact(fact_id: int, db: Session = Depends(get_db)) -> FactRead:
    fact = db.get(Fact, fact_id)
    if not fact:
        raise HTTPException(status_code=404, detail="Fact not found")
    fact.status = FactStatus.REJECTED.value
    db.add(fact)
    db.commit()
    db.refresh(fact)
    return serialize_fact(fact)


# --- Review Batches ---

@app.get("/api/review-batches", response_model=list[ReviewBatchRead])
def list_review_batches(
    batch_type: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[ReviewBatchRead]:
    stmt = select(ReviewBatch)
    if batch_type:
        stmt = stmt.where(ReviewBatch.batch_type == batch_type)
    if status:
        stmt = stmt.where(ReviewBatch.status == status)
    stmt = stmt.order_by(ReviewBatch.created_at.desc()).limit(limit)
    return [serialize_review_batch(b) for b in db.scalars(stmt).all()]


@app.post("/api/review-batches", response_model=ReviewBatchRead, status_code=201)
def create_review_batch(payload: ReviewBatchCreate, db: Session = Depends(get_db)) -> ReviewBatchRead:
    batch = ReviewBatch(
        batch_type=payload.batch_type,
        title=payload.title,
        period_start=payload.period_start,
        period_end=payload.period_end,
        status=payload.status,
        material_count=payload.material_count,
        created_by=payload.created_by,
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return serialize_review_batch(batch)


@app.get("/api/review-batches/{batch_id}", response_model=ReviewBatchRead)
def get_review_batch(batch_id: int, db: Session = Depends(get_db)) -> ReviewBatchRead:
    batch = db.get(ReviewBatch, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Review batch not found")
    return serialize_review_batch(batch)


@app.patch("/api/review-batches/{batch_id}", response_model=ReviewBatchRead)
def update_review_batch(batch_id: int, payload: ReviewBatchUpdate, db: Session = Depends(get_db)) -> ReviewBatchRead:
    batch = db.get(ReviewBatch, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Review batch not found")
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(batch, field, value)
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return serialize_review_batch(batch)


@app.get("/api/review-batches/{batch_id}/customer-materials", response_model=list[CustomerMaterialRead])
def list_batch_materials(batch_id: int, db: Session = Depends(get_db)) -> list[CustomerMaterialRead]:
    batch = db.get(ReviewBatch, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Review batch not found")
    stmt = select(CustomerMaterial).where(
        CustomerMaterial.review_batch_id == batch_id  # type: ignore[attr-defined]
    ).order_by(CustomerMaterial.id.asc())
    return [serialize_customer_material(m) for m in db.scalars(stmt).all()]


# --- Customer Material V2 Create / Read / Update / Mark Uploaded ---

@app.post("/api/customer-materials-v2", response_model=CustomerMaterialV2Read, status_code=201)
def create_customer_material_v2(payload: CustomerMaterialV2Create, db: Session = Depends(get_db)) -> CustomerMaterialV2Read:
    customer = db.get(Customer, payload.customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    project_str = customer.area or customer.name
    material = CustomerMaterial(
        project=project_str,
        title=payload.title,
        customer_id=payload.customer_id,
        project_v2_id=payload.project_v2_id,
        review_batch_id=payload.review_batch_id,
        material_type=payload.material_type,
        period_start=payload.period_start,
        period_end=payload.period_end,
        raw_facts_markdown=payload.raw_facts_markdown,
        summary_markdown=payload.summary_markdown,
        insights_markdown=payload.insights_markdown,
        status=payload.status,
        generation_meta_json=json.dumps(payload.generation_meta, ensure_ascii=False) if payload.generation_meta else None,
        # old compat defaults
        source_type="text",
        source="chat",
        source_refs_json="{}",
        value_types_json="[]",
    )
    db.add(material)
    db.commit()
    db.refresh(material)
    return serialize_material_v2(material)


@app.get("/api/customer-materials-v2/{material_id}", response_model=CustomerMaterialV2Read)
def get_customer_material_v2(material_id: int, db: Session = Depends(get_db)) -> CustomerMaterialV2Read:
    material = get_customer_material_or_404(db, material_id)
    return serialize_material_v2(material)


@app.patch("/api/customer-materials-v2/{material_id}", response_model=CustomerMaterialV2Read)
def update_customer_material_v2(material_id: int, payload: CustomerMaterialV2Update, db: Session = Depends(get_db)) -> CustomerMaterialV2Read:
    material = get_customer_material_or_404(db, material_id)
    updates = payload.model_dump(exclude_unset=True)
    clear_project_v2 = bool(updates.pop("clear_project_v2", False))
    clear_batch = bool(updates.pop("clear_batch", False))
    if "generation_meta" in updates:
        meta = updates.pop("generation_meta")
        material.generation_meta_json = json.dumps(meta, ensure_ascii=False) if meta else None  # type: ignore[attr-defined]
    for field, value in updates.items():
        setattr(material, field, value)
    if clear_project_v2:
        material.project_v2_id = None  # type: ignore[attr-defined]
    if clear_batch:
        material.review_batch_id = None  # type: ignore[attr-defined]
    db.add(material)
    db.commit()
    db.refresh(material)
    return serialize_material_v2(material)


@app.post("/api/customer-materials-v2/{material_id}/mark-uploaded", response_model=CustomerMaterialV2Read)
def mark_material_uploaded(material_id: int, db: Session = Depends(get_db)) -> CustomerMaterialV2Read:
    material = get_customer_material_or_404(db, material_id)
    material.status = CustomerMaterialStatus.UPLOADED.value
    db.add(material)
    db.commit()
    db.refresh(material)
    return serialize_material_v2(material)


# --- Customer Material Facts ---

@app.post("/api/customer-materials-v2/{material_id}/facts", response_model=CustomerMaterialFactRead, status_code=201)
def add_material_fact(material_id: int, payload: CustomerMaterialFactCreate, db: Session = Depends(get_db)) -> CustomerMaterialFactRead:
    material = get_customer_material_or_404(db, material_id)
    fact = db.get(Fact, payload.fact_id)
    if not fact:
        raise HTTPException(status_code=404, detail="Fact not found")
    mf = CustomerMaterialFact(
        material_id=material.id,
        fact_id=payload.fact_id,
        sort_order=payload.sort_order,
    )
    db.add(mf)
    db.commit()
    db.refresh(mf)
    return serialize_material_fact(mf)


@app.get("/api/customer-materials-v2/{material_id}/facts", response_model=list[CustomerMaterialFactRead])
def list_material_facts(material_id: int, db: Session = Depends(get_db)) -> list[CustomerMaterialFactRead]:
    get_customer_material_or_404(db, material_id)
    stmt = select(CustomerMaterialFact).where(
        CustomerMaterialFact.material_id == material_id
    ).order_by(CustomerMaterialFact.sort_order.asc())
    return [serialize_material_fact(mf) for mf in db.scalars(stmt).all()]


if __name__ == "__main__":
    import uvicorn

    init_db()
    uvicorn.run("main:app", host=settings.api_host, port=settings.api_port, reload=True)
