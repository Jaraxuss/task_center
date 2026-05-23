"""Customer (V2) domain services."""

from __future__ import annotations

from models import Customer
from schemas import CustomerRead


def serialize_customer(customer: Customer) -> CustomerRead:
    return CustomerRead(
        id=customer.id,
        name=customer.name,
        key=customer.key,
        aliases=customer.aliases or [],
        status=customer.status,
        description=customer.description,
        area=customer.area,
        tags=customer.tags or [],
        nblm_notebook_id=customer.nblm_notebook_id,
        created_at=customer.created_at,
        updated_at=customer.updated_at,
    )


__all__ = ["serialize_customer"]
