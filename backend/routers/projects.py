"""Project endpoints.

Consolidated from the former ``projects_v2.py`` (FK-based CRUD) and the
legacy ``projects.py`` (string-based summary list).  The URL prefix is now
``/api/projects``; the old ``/api/projects-v2`` path is kept as a
backward-compat redirect via a secondary router.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from db import get_db
from models import Customer, Project
from schemas import (
    ProjectCreate,
    ProjectRead,
    ProjectSummary,
    ProjectUpdate,
    normalize_project_name,
)
from services.common import get_or_404
from services.dashboard import build_project_summaries
from services.projects import serialize_project

router = APIRouter(prefix="/api/projects", tags=["projects"])

# ---------------------------------------------------------------------------
# Backward-compat: /api/projects-v2 still works (same handlers)
# ---------------------------------------------------------------------------
legacy_v2_router = APIRouter(prefix="/api/projects-v2", tags=["projects-v2"])


# ---------------------------------------------------------------------------
# Summary (migrated from old projects.py)
# ---------------------------------------------------------------------------


@router.get("/summary", response_model=list[ProjectSummary])
def list_project_summaries(db: Session = Depends(get_db)) -> list[ProjectSummary]:
    """Lightweight project summaries with task counts (used by board hero)."""
    return build_project_summaries(db)


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


@router.get("", response_model=list[ProjectRead])
def list_projects(
    customer_id: int | None = Query(default=None),
    area: str | None = Query(default=None),
    status: str | None = Query(default=None),
    q: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[ProjectRead]:
    stmt = select(Project)
    if customer_id is not None:
        stmt = stmt.where(Project.customer_id == customer_id)
    if area:
        normalized = normalize_project_name(area)
        if normalized:
            stmt = stmt.where(Project.area == normalized)
    if status:
        stmt = stmt.where(Project.status == status)
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(Project.name.ilike(pattern))
    stmt = stmt.order_by(Project.created_at.desc())
    return [serialize_project(p) for p in db.scalars(stmt).all()]


@router.post("", response_model=ProjectRead, status_code=201)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)) -> ProjectRead:
    area = payload.area
    if area is None and payload.customer_id is not None:
        customer = db.get(Customer, payload.customer_id)
        if customer and customer.area:
            area = customer.area
    project = Project(
        customer_id=payload.customer_id,
        project_type=payload.project_type,
        name=payload.name,
        status=payload.status,
        area=area,
        tags=payload.tags,
        start_at=payload.start_at,
        target_end_at=payload.target_end_at,
        actual_end_at=payload.actual_end_at,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return serialize_project(project)


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(project_id: int, db: Session = Depends(get_db)) -> ProjectRead:
    project = get_or_404(db, Project, project_id, name="Project")
    return serialize_project(project)


@router.patch("/{project_id}", response_model=ProjectRead)
def update_project(project_id: int, payload: ProjectUpdate, db: Session = Depends(get_db)) -> ProjectRead:
    project = get_or_404(db, Project, project_id, name="Project")
    updates = payload.model_dump(exclude_unset=True)
    clear_customer = bool(updates.pop("clear_customer", False))
    for field, value in updates.items():
        setattr(project, field, value)
    if clear_customer:
        project.customer_id = None
    db.add(project)
    db.commit()
    db.refresh(project)
    return serialize_project(project)


# ---------------------------------------------------------------------------
# Backward-compat /api/projects-v2 handlers (thin wrappers)
# ---------------------------------------------------------------------------


@legacy_v2_router.get("", response_model=list[ProjectRead])
def list_projects_v2_compat(
    customer_id: int | None = Query(default=None),
    area: str | None = Query(default=None),
    status: str | None = Query(default=None),
    q: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[ProjectRead]:
    return list_projects(customer_id=customer_id, area=area, status=status, q=q, db=db)


@legacy_v2_router.get("/{project_id}", response_model=ProjectRead)
def get_project_v2_compat(project_id: int, db: Session = Depends(get_db)) -> ProjectRead:
    return get_project(project_id=project_id, db=db)


@legacy_v2_router.post("", response_model=ProjectRead, status_code=201)
def create_project_v2_compat(payload: ProjectCreate, db: Session = Depends(get_db)) -> ProjectRead:
    return create_project(payload=payload, db=db)


@legacy_v2_router.patch("/{project_id}", response_model=ProjectRead)
def update_project_v2_compat(project_id: int, payload: ProjectUpdate, db: Session = Depends(get_db)) -> ProjectRead:
    return update_project(project_id=project_id, payload=payload, db=db)
