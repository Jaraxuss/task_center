"""Knowledge facts overview and knowledge preferences schemas."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class KnowledgeFactProjectOverview(BaseModel):
    project_id: int | None
    project_name: str
    status: str | None
    fact_count: int
    latest_fact_at: datetime | None


class KnowledgeFactCustomerOverview(BaseModel):
    customer_id: int | None
    customer_name: str
    area: str | None
    fact_count: int
    project_count: int
    latest_fact_at: datetime | None
    projects: list[KnowledgeFactProjectOverview]


class KnowledgeFactsOverview(BaseModel):
    total_fact_count: int
    customers: list[KnowledgeFactCustomerOverview]


class KnowledgePreferenceRead(BaseModel):
    pinned_customer_ids: list[int] = Field(default_factory=list)
    customer_order_ids: list[int] = Field(default_factory=list)


class KnowledgePreferenceUpdate(BaseModel):
    pinned_customer_ids: list[int] | None = None
    customer_order_ids: list[int] | None = None

    @field_validator("pinned_customer_ids", "customer_order_ids")
    @classmethod
    def normalize_id_list(cls, value: list[int] | None) -> list[int] | None:
        if value is None:
            return None
        normalized: list[int] = []
        for item in value:
            cid = int(item)
            if cid > 0 and cid not in normalized:
                normalized.append(cid)
        return normalized
