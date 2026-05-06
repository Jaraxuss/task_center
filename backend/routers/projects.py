"""Legacy project (string-based) endpoints.

Projects here are the legacy string label associated with each task
(``Task.project``). The newer ``ProjectV2`` aggregate lives under
``/api/projects-v2``.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from db import get_db
from models import EventType, Task
from schemas import ProjectRenameRequest, ProjectRenameResponse, ProjectSummary
from services.board import get_board_preference, serialize_board_preference
from services.dashboard import build_project_summaries
from services.tasks import add_event, task_load_options

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("", response_model=list[ProjectSummary])
def list_projects(db: Session = Depends(get_db)) -> list[ProjectSummary]:
    return build_project_summaries(db)


@router.patch("/rename", response_model=ProjectRenameResponse)
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
