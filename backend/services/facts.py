"""Fact (V2) domain services."""

from __future__ import annotations

from models import Fact
from schemas import FactRead


def serialize_fact(fact: Fact) -> FactRead:
    return FactRead(
        id=fact.id,
        customer_id=fact.customer_id,
        project_id=fact.project_id,
        task_id=fact.task_id,
        fact_date=fact.fact_date,
        title=fact.title,
        raw_markdown=fact.raw_markdown,
        source_type=fact.source_type,
        value_types=fact.value_types or [],
        status=fact.status,
        created_at=fact.created_at,
        updated_at=fact.updated_at,
    )


__all__ = ["serialize_fact"]
