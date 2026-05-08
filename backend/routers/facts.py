"""Fact (V2) endpoints."""

from __future__ import annotations

import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from db import get_db
from models import Fact, Task
from schemas import FactCreate, FactRead, FactUpdate
from services.common import get_or_404
from services.facts import serialize_fact

router = APIRouter(prefix="/api/facts", tags=["facts"])


@router.get("", response_model=list[FactRead])
def list_facts(
    customer_id: int | None = Query(default=None),
    project_id: int | None = Query(default=None),
    project_unassigned: bool = Query(default=False),
    task_id: int | None = Query(default=None),
    status: str | None = Query(default=None),
    source_type: str | None = Query(default=None),
    from_date: datetime | None = Query(default=None, alias="from"),
    to_date: datetime | None = Query(default=None, alias="to"),
    q: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[FactRead]:
    if project_id is not None and project_unassigned:
        raise HTTPException(status_code=400, detail="cannot specify both project_id and project_unassigned")

    stmt = select(Fact)
    if customer_id is not None:
        stmt = stmt.where(Fact.customer_id == customer_id)
    if project_id is not None:
        stmt = stmt.where(Fact.project_id == project_id)
    if project_unassigned:
        stmt = stmt.where(Fact.project_id.is_(None))
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


@router.post("", response_model=FactRead, status_code=201)
def create_fact(payload: FactCreate, db: Session = Depends(get_db)) -> FactRead:
    customer_id = payload.customer_id
    project_id = payload.project_id
    if payload.task_id is not None and (customer_id is None or project_id is None):
        task = get_or_404(db, Task, payload.task_id)
        customer_id = customer_id if customer_id is not None else task.customer_id
        project_id = project_id if project_id is not None else task.project_id

    fact = Fact(
        customer_id=customer_id,
        project_id=project_id,
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


@router.get("/{fact_id}", response_model=FactRead)
def get_fact(fact_id: int, db: Session = Depends(get_db)) -> FactRead:
    fact = get_or_404(db, Fact, fact_id)
    return serialize_fact(fact)


@router.patch("/{fact_id}", response_model=FactRead)
def update_fact(fact_id: int, payload: FactUpdate, db: Session = Depends(get_db)) -> FactRead:
    fact = get_or_404(db, Fact, fact_id)
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


@router.delete("/{fact_id}", status_code=204)
def delete_fact(fact_id: int, db: Session = Depends(get_db)) -> Response:
    fact = get_or_404(db, Fact, fact_id)
    db.delete(fact)
    db.commit()
    return Response(status_code=204)
