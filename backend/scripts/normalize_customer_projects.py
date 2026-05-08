from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from db import SessionLocal
from main import rename_project, update_task
from models import Task
from schemas import ProjectRenameRequest, TaskUpdate

EXCLUDED_PROJECTS = {"生活", "闲鱼", "影刀6.0灰度"}
CUSTOMER_PREFIX = "客户_"
CUSTOMER_TAG = "客户"


def load_tags(task: Task) -> list[str]:
    return list(task.tags or [])


def main() -> None:
    db = SessionLocal()
    try:
        projects = [
            name
            for name in db.scalars(select(Task.project).where(Task.project.is_not(None)).distinct().order_by(Task.project.asc()))
            if name
        ]

        renamed_projects: list[dict[str, object]] = []
        affected_task_count = 0
        for old_name in projects:
            if old_name in EXCLUDED_PROJECTS or old_name.startswith(CUSTOMER_PREFIX):
                continue
            response = rename_project(ProjectRenameRequest(old_name=old_name, new_name=f"{CUSTOMER_PREFIX}{old_name}"), db)
            renamed_projects.append(
                {
                    "old_name": response.old_name,
                    "new_name": response.new_name,
                    "updated_task_count": response.updated_task_count,
                }
            )
            affected_task_count += response.updated_task_count

        customer_tasks = list(
            db.scalars(
                select(Task)
                .where(Task.project.is_not(None), Task.project.like(f"{CUSTOMER_PREFIX}%"))
                .options(selectinload(Task.reminders), selectinload(Task.events))
                .order_by(Task.id.asc())
            ).unique()
        )

        tagged_task_ids: list[int] = []
        for task in customer_tasks:
            tags = load_tags(task)
            if CUSTOMER_TAG in tags:
                continue
            update_task(task.id, TaskUpdate(tags=[*tags, CUSTOMER_TAG]), db)
            tagged_task_ids.append(task.id)

        print(
            json.dumps(
                {
                    "renamed_projects": renamed_projects,
                    "affected_task_count": affected_task_count,
                    "customer_tag_added_task_count": len(tagged_task_ids),
                    "customer_tag_added_task_ids": tagged_task_ids,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
