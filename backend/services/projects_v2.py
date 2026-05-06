"""Project (V2) domain services."""

from __future__ import annotations

from models import Project as ProjectV2
from schemas import ProjectV2Read
from services.json_utils import parse_json_list


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


__all__ = ["serialize_project_v2"]
