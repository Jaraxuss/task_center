"""Customer (V2) domain services."""

from __future__ import annotations

from models import Customer
from schemas import CustomerRead
from services.json_utils import parse_json_list


def serialize_customer(customer: Customer) -> CustomerRead:
    return CustomerRead(
        id=customer.id,
        name=customer.name,
        key=customer.key,
        aliases=parse_json_list(customer.aliases_json),
        status=customer.status,
        description=customer.description,
        area=customer.area,
        tags=parse_json_list(customer.tags_json),
        created_at=customer.created_at,
        updated_at=customer.updated_at,
    )


__all__ = ["serialize_customer"]
