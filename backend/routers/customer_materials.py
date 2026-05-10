"""Customer-material endpoints (period summaries, fact attachments)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from db import get_db
from models import (
    CustomerMaterial,
    CustomerMaterialFact,
    CustomerMaterialStatus,
    Fact,
)
from schemas import (
    CustomerMaterialCreate,
    CustomerMaterialFactCreate,
    CustomerMaterialFactRead,
    CustomerMaterialRead,
    CustomerMaterialUpdate,
)
from services.common import get_or_404
from services.customer_materials import (
    get_customer_material_or_404,
    serialize_customer_material,
    serialize_material_fact,
    validate_customer_material_references,
    validate_customer_material_status,
)
from timeutils import now_utc

router = APIRouter(prefix="/api/customer-materials", tags=["customer-materials"])


@router.get("", response_model=list[CustomerMaterialRead])
def list_customer_materials(
    q: str | None = Query(default=None),
    status: str | None = Query(default=None),
    include_archived: bool = False,
    limit: int = Query(default=100, ge=1, le=500),
    customer_id: int | None = Query(default=None),
    project_v2_id: int | None = Query(default=None),
    review_batch_id: int | None = Query(default=None),
    material_type: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[CustomerMaterialRead]:
    validate_customer_material_status(status)
    stmt = select(CustomerMaterial)
    if status:
        stmt = stmt.where(CustomerMaterial.status == status)
    if customer_id is not None:
        stmt = stmt.where(CustomerMaterial.customer_id == customer_id)
    if project_v2_id is not None:
        stmt = stmt.where(CustomerMaterial.project_v2_id == project_v2_id)
    if review_batch_id is not None:
        stmt = stmt.where(CustomerMaterial.review_batch_id == review_batch_id)
    if material_type:
        stmt = stmt.where(CustomerMaterial.material_type == material_type)
    if not include_archived:
        stmt = stmt.where(CustomerMaterial.archived_at.is_(None))
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                CustomerMaterial.title.like(pattern),
                CustomerMaterial.raw_facts_markdown.like(pattern),
            )
        )
    stmt = stmt.order_by(CustomerMaterial.updated_at.desc(), CustomerMaterial.id.desc()).limit(limit)
    return [serialize_customer_material(material) for material in db.scalars(stmt).all()]


@router.post("", response_model=CustomerMaterialRead, status_code=201)
def create_customer_material(payload: CustomerMaterialCreate, db: Session = Depends(get_db)) -> CustomerMaterialRead:
    validate_customer_material_status(payload.status)
    validate_customer_material_references(
        db,
        customer_id=payload.customer_id,
        project_v2_id=payload.project_v2_id,
        review_batch_id=payload.review_batch_id,
    )
    material = CustomerMaterial(
        project="",
        source_type="text",
        source="system",
        source_refs={},
        value_types=[],
        task_id=None,
        title=payload.title,
        material_date=payload.material_date,
        status=payload.status,
        customer_id=payload.customer_id,
        project_v2_id=payload.project_v2_id,
        review_batch_id=payload.review_batch_id,
        material_type=payload.material_type,
        period_start=payload.period_start,
        period_end=payload.period_end,
        raw_facts_markdown=payload.raw_facts_markdown,
        generation_meta=payload.generation_meta,
    )
    db.add(material)
    db.commit()
    db.refresh(material)
    return serialize_customer_material(material)


@router.get("/{material_id}", response_model=CustomerMaterialRead)
def get_customer_material(material_id: int, db: Session = Depends(get_db)) -> CustomerMaterialRead:
    return serialize_customer_material(get_customer_material_or_404(db, material_id))


@router.patch("/{material_id}", response_model=CustomerMaterialRead)
def update_customer_material(
    material_id: int, payload: CustomerMaterialUpdate, db: Session = Depends(get_db)
) -> CustomerMaterialRead:
    material = get_customer_material_or_404(db, material_id)
    updates = payload.model_dump(exclude_unset=True)
    clear_project_v2 = bool(updates.pop("clear_project_v2", False))
    clear_batch = bool(updates.pop("clear_batch", False))
    if "status" in updates:
        validate_customer_material_status(updates["status"])
    validate_customer_material_references(
        db,
        customer_id=updates.get("customer_id") if "customer_id" in updates else None,
        project_v2_id=updates.get("project_v2_id") if "project_v2_id" in updates else None,
        review_batch_id=updates.get("review_batch_id") if "review_batch_id" in updates else None,
    )
    if clear_project_v2:
        material.project_v2_id = None
    if clear_batch:
        material.review_batch_id = None
    for field, value in updates.items():
        setattr(material, field, value)
    db.add(material)
    db.commit()
    db.refresh(material)
    return serialize_customer_material(material)


@router.delete("/{material_id}", response_model=CustomerMaterialRead)
def archive_customer_material(material_id: int, db: Session = Depends(get_db)) -> CustomerMaterialRead:
    material = get_customer_material_or_404(db, material_id)
    if material.archived_at is None:
        material.archived_at = now_utc()
        db.add(material)
        db.commit()
        db.refresh(material)
    return serialize_customer_material(material)


@router.post("/{material_id}/mark-uploaded", response_model=CustomerMaterialRead)
def mark_material_uploaded(material_id: int, db: Session = Depends(get_db)) -> CustomerMaterialRead:
    """Mark a customer material as uploaded."""
    material = get_customer_material_or_404(db, material_id)
    material.status = CustomerMaterialStatus.UPLOADED.value
    db.add(material)
    db.commit()
    db.refresh(material)
    return serialize_customer_material(material)


@router.post("/{material_id}/facts", response_model=CustomerMaterialFactRead, status_code=201)
def add_material_fact(
    material_id: int, payload: CustomerMaterialFactCreate, db: Session = Depends(get_db)
) -> CustomerMaterialFactRead:
    """Add a fact to a customer material."""
    material = get_customer_material_or_404(db, material_id)
    get_or_404(db, Fact, payload.fact_id)
    mf = CustomerMaterialFact(
        material_id=material.id,
        fact_id=payload.fact_id,
        sort_order=payload.sort_order,
    )
    db.add(mf)
    db.commit()
    db.refresh(mf)
    return serialize_material_fact(mf)


@router.get("/{material_id}/facts", response_model=list[CustomerMaterialFactRead])
def list_material_facts(material_id: int, db: Session = Depends(get_db)) -> list[CustomerMaterialFactRead]:
    """List facts associated with a customer material."""
    get_customer_material_or_404(db, material_id)
    stmt = (
        select(CustomerMaterialFact)
        .where(CustomerMaterialFact.material_id == material_id)
        .order_by(CustomerMaterialFact.sort_order.asc())
    )
    return [serialize_material_fact(mf) for mf in db.scalars(stmt).all()]
