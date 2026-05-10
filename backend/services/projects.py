"""Project domain services."""

from __future__ import annotations

from models import Project
from schemas import ProjectRead


def serialize_project(project: Project) -> ProjectRead:
    return ProjectRead(
        id=project.id,
        customer_id=project.customer_id,
        project_type=project.project_type,
        name=project.name,
        status=project.status,
        area=project.area,
        tags=project.tags or [],
        start_at=project.start_at,
        target_end_at=project.target_end_at,
        actual_end_at=project.actual_end_at,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


# Backward-compat alias
serialize_project_v2 = serialize_project

__all__ = ["serialize_project", "serialize_project_v2"]
