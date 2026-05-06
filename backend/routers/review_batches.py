"""Review batch (V2) endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from db import get_db
from models import CustomerMaterial, ReviewBatch
from schemas import (
    CustomerMaterialRead,
    ReviewBatchCreate,
    ReviewBatchRead,
    ReviewBatchUpdate,
)
from services.customer_materials import serialize_customer_material
from services.review_batches import serialize_review_batch

router = APIRouter(prefix="/api/review-batches", tags=["review-batches"])


@router.get("", response_model=list[ReviewBatchRead])
def list_review_batches(
    batch_type: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[ReviewBatchRead]:
    stmt = select(ReviewBatch)
    if batch_type:
        stmt = stmt.where(ReviewBatch.batch_type == batch_type)
    if status:
        stmt = stmt.where(ReviewBatch.status == status)
    stmt = stmt.order_by(ReviewBatch.created_at.desc()).limit(limit)
    return [serialize_review_batch(b) for b in db.scalars(stmt).all()]


@router.post("", response_model=ReviewBatchRead, status_code=201)
def create_review_batch(payload: ReviewBatchCreate, db: Session = Depends(get_db)) -> ReviewBatchRead:
    batch = ReviewBatch(
        batch_type=payload.batch_type,
        title=payload.title,
        period_start=payload.period_start,
        period_end=payload.period_end,
        status=payload.status,
        material_count=payload.material_count,
        created_by=payload.created_by,
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return serialize_review_batch(batch)


@router.get("/{batch_id}", response_model=ReviewBatchRead)
def get_review_batch(batch_id: int, db: Session = Depends(get_db)) -> ReviewBatchRead:
    batch = db.get(ReviewBatch, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Review batch not found")
    return serialize_review_batch(batch)


@router.patch("/{batch_id}", response_model=ReviewBatchRead)
def update_review_batch(batch_id: int, payload: ReviewBatchUpdate, db: Session = Depends(get_db)) -> ReviewBatchRead:
    batch = db.get(ReviewBatch, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Review batch not found")
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(batch, field, value)
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return serialize_review_batch(batch)


@router.get("/{batch_id}/customer-materials", response_model=list[CustomerMaterialRead])
def list_batch_materials(batch_id: int, db: Session = Depends(get_db)) -> list[CustomerMaterialRead]:
    batch = db.get(ReviewBatch, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Review batch not found")
    stmt = (
        select(CustomerMaterial)
        .where(CustomerMaterial.review_batch_id == batch_id)
        .order_by(CustomerMaterial.id.asc())
    )
    return [serialize_customer_material(m) for m in db.scalars(stmt).all()]
