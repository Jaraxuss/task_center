"""Customer (V2) endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from db import get_db
from models import Customer
from schemas import CustomerCreate, CustomerRead, CustomerUpdate
from services.common import get_or_404
from services.customers import serialize_customer

router = APIRouter(prefix="/api/customers", tags=["customers"])


@router.get("", response_model=list[CustomerRead])
def list_customers(
    q: str | None = Query(default=None),
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[CustomerRead]:
    stmt = select(Customer)
    if status:
        stmt = stmt.where(Customer.status == status)
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Customer.name.ilike(pattern),
                Customer.key.ilike(pattern),
                Customer.area.ilike(pattern),
                Customer.aliases.like(pattern),
            )
        )
    stmt = stmt.order_by(Customer.name.asc())
    return [serialize_customer(c) for c in db.scalars(stmt).all()]


@router.post("", response_model=CustomerRead, status_code=201)
def create_customer(payload: CustomerCreate, db: Session = Depends(get_db)) -> CustomerRead:
    area = payload.area or f"\u5ba2\u6237_{payload.name}"
    aliases = list(payload.aliases)
    if area not in aliases:
        aliases.append(area)
    customer = Customer(
        name=payload.name,
        key=payload.key,
        aliases=aliases,
        status=payload.status,
        description=payload.description,
        area=area,
        tags=payload.tags,
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return serialize_customer(customer)


@router.get("/{customer_id}", response_model=CustomerRead)
def get_customer(customer_id: int, db: Session = Depends(get_db)) -> CustomerRead:
    customer = get_or_404(db, Customer, customer_id)
    return serialize_customer(customer)


@router.patch("/{customer_id}", response_model=CustomerRead)
def update_customer(customer_id: int, payload: CustomerUpdate, db: Session = Depends(get_db)) -> CustomerRead:
    customer = get_or_404(db, Customer, customer_id)
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(customer, field, value)
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return serialize_customer(customer)
