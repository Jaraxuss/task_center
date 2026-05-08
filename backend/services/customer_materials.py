"""Customer-material domain services.

Owns serialization, lookup-or-404, and reference-validation for the
``customer_materials`` aggregate.
"""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from models import (
    Customer,
    CustomerMaterial,
    CustomerMaterialFact,
    CustomerMaterialStatus,
    ReviewBatch,
    Task,
)
from models import (
    Project as ProjectV2,
)
from schemas import CustomerMaterialFactRead, CustomerMaterialRead


def serialize_customer_material(material: CustomerMaterial) -> CustomerMaterialRead:
    return CustomerMaterialRead(
        id=material.id,
        project=material.project,
        title=material.title,
        material_date=material.material_date,
        source_type=material.source_type,
        source=material.source,
        source_refs=material.source_refs or {},
        value_types=material.value_types or [],
        status=material.status,
        task_id=material.task_id,
        created_at=material.created_at,
        updated_at=material.updated_at,
        archived_at=material.archived_at,
        # V2 fields
        customer_id=getattr(material, "customer_id", None),
        project_v2_id=getattr(material, "project_v2_id", None),
        review_batch_id=getattr(material, "review_batch_id", None),
        material_type=getattr(material, "material_type", None),
        period_start=getattr(material, "period_start", None),
        period_end=getattr(material, "period_end", None),
        raw_facts_markdown=getattr(material, "raw_facts_markdown", None),
        generation_meta=material.generation_meta,
    )


def serialize_material_fact(mf: CustomerMaterialFact) -> CustomerMaterialFactRead:
    return CustomerMaterialFactRead(
        id=mf.id,
        material_id=mf.material_id,
        fact_id=mf.fact_id,
        sort_order=mf.sort_order,
        created_at=mf.created_at,
    )


def get_customer_material_or_404(db: Session, material_id: int) -> CustomerMaterial:
    material = db.scalar(select(CustomerMaterial).where(CustomerMaterial.id == material_id))
    if not material:
        raise HTTPException(status_code=404, detail="Customer material not found")
    return material


def validate_task_reference(db: Session, task_id: int | None) -> None:
    if task_id is None:
        return
    if not db.get(Task, task_id):
        raise HTTPException(status_code=404, detail="Referenced task not found")


def validate_customer_material_references(
    db: Session,
    *,
    customer_id: int | None = None,
    project_v2_id: int | None = None,
    review_batch_id: int | None = None,
) -> Customer | None:
    customer: Customer | None = None
    if customer_id is not None:
        customer = db.get(Customer, customer_id)
        if not customer:
            raise HTTPException(status_code=404, detail="Referenced customer not found")
    if project_v2_id is not None and not db.get(ProjectV2, project_v2_id):
        raise HTTPException(status_code=404, detail="Referenced project not found")
    if review_batch_id is not None and not db.get(ReviewBatch, review_batch_id):
        raise HTTPException(status_code=404, detail="Referenced review batch not found")
    return customer


def validate_customer_material_status(status: str | None) -> None:
    if status is None:
        return
    if status not in {item.value for item in CustomerMaterialStatus}:
        raise HTTPException(status_code=400, detail="Invalid customer material status")


__all__ = [
    "get_customer_material_or_404",
    "serialize_customer_material",
    "serialize_material_fact",
    "validate_customer_material_references",
    "validate_customer_material_status",
    "validate_task_reference",
]
