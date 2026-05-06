"""Project V2 endpoints."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from db import get_db
from models import Customer
from models import Project as ProjectV2
from schemas import (
    ProjectV2Create,
    ProjectV2Read,
    ProjectV2Update,
    normalize_project_name,
)
from services.projects_v2 import serialize_project_v2

router = APIRouter(prefix="/api/projects-v2", tags=["projects-v2"])


@router.get("", response_model=list[ProjectV2Read])
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


@router.post("", response_model=ProjectV2Read, status_code=201)
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


@router.get("/{project_id}", response_model=ProjectV2Read)
def get_project_v2(project_id: int, db: Session = Depends(get_db)) -> ProjectV2Read:
    project = db.get(ProjectV2, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return serialize_project_v2(project)


@router.patch("/{project_id}", response_model=ProjectV2Read)
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
