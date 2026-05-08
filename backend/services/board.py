"""Board / preferences services.

The kanban board view depends on a ``BoardPreference`` row that records
custom task ordering, pinned projects, and project ordering. This module
owns reading/writing that row, plus the deterministic sort used by the
board endpoint.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from models import BoardPreference, Task
from schemas import BoardPreferenceRead
from services.tasks import task_schedule_at
from timeutils import UTC


def get_board_preference(db: Session) -> BoardPreference:
    preference = db.scalar(select(BoardPreference).limit(1))
    if preference is None:
        preference = BoardPreference()
        db.add(preference)
        db.flush()
    return preference


def serialize_board_preference(preference: BoardPreference) -> BoardPreferenceRead:
    task_order = [int(item) for item in (preference.task_order or []) if int(item) > 0]
    pinned_projects = [str(item).strip() for item in (preference.pinned_projects or []) if str(item).strip()]
    project_order = [str(item).strip() for item in (preference.project_order or []) if str(item).strip()]

    normalized_projects: list[str] = []
    for project in pinned_projects:
        if project not in normalized_projects:
            normalized_projects.append(project)

    normalized_project_order: list[str] = []
    for project in project_order:
        if project not in normalized_project_order:
            normalized_project_order.append(project)

    return BoardPreferenceRead(
        task_order=task_order,
        pinned_projects=normalized_projects,
        project_order=normalized_project_order,
    )


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
