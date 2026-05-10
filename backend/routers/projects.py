"""Legacy project (string-based) list endpoint.

The GET endpoint is still consumed by the mobile board view.
The ``PATCH /rename`` endpoint was removed — project renaming now
goes through the V2 project model directly.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from db import get_db
from schemas import ProjectSummary
from services.dashboard import build_project_summaries

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("", response_model=list[ProjectSummary])
def list_projects(db: Session = Depends(get_db)) -> list[ProjectSummary]:
    return build_project_summaries(db)
