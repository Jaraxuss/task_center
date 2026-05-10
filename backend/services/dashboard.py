"""Dashboard summary builders.

These pure-function builders synthesize the read-models that back the
dashboard endpoints (today / plan / board / history / projects). They
operate over the task ORM via ``services.tasks`` and the board sort
metadata via ``services.board``.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from models import Project, Task, TaskStatus
from schemas import (
    BoardSummary,
    HistorySummary,
    PlanGroup,
    PlanSummary,
    ProjectSummary,
    TaskBoardGroup,
    TodaySummary,
)
from services.board import get_board_sort_metadata, sort_tasks_for_board
from services.tasks import (
    query_tasks,
    serialize_task,
    task_load_options,
    task_schedule_at,
    today_local,
)
from timeutils import UTC, local_date, local_day_bounds


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
    return PlanSummary(date=target, total=total, open_count=total, plan_groups=plan_groups)


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
        grouped.append(
            TaskBoardGroup(
                status=status,
                tasks=[serialize_task(task) for task in sort_tasks_for_board(status_tasks, task_order_map)],
            )
        )
    return BoardSummary(groups=grouped)


def build_history_summary(
    db: Session,
    *,
    target: date | None = None,
    status: str | None = None,
    query: str | None = None,
) -> HistorySummary:
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
    # Primary: group by project_id → Project.name
    tasks_with_pid = list(
        db.scalars(
            select(Task).where(Task.project_id.is_not(None))
        ).unique()
    )
    project_ids = {t.project_id for t in tasks_with_pid if t.project_id is not None}
    project_map: dict[int, Project] = {}
    if project_ids:
        for proj in db.scalars(select(Project).where(Project.id.in_(project_ids))):
            project_map[proj.id] = proj

    grouped: dict[str, list[Task]] = {}
    for task in tasks_with_pid:
        proj = project_map.get(task.project_id)  # type: ignore[arg-type]
        name = proj.name if proj else None
        if not name:
            continue
        grouped.setdefault(name, []).append(task)

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
