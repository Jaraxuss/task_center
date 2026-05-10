"""Customer-material schemas (legacy + V2 fields consolidated)."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from ._common import (
    CustomerMaterialStatusValue,
    MaterialTypeValue,
    normalize_datetime_input,
    normalize_required_text,
)


class CustomerMaterialBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    material_date: datetime | None = None
    status: CustomerMaterialStatusValue = "pending"
    customer_id: int | None = None
    project_v2_id: int | None = None
    review_batch_id: int | None = None
    material_type: MaterialTypeValue = "period_summary"
    period_start: datetime | None = None
    period_end: datetime | None = None
    raw_facts_markdown: str | None = None
    generation_meta: dict[str, Any] | None = None

    @field_validator("title", mode="before")
    @classmethod
    def normalize_title(cls, value: str | None) -> str:
        return normalize_required_text(value, field_name="title")

    @field_validator("material_date", mode="before")
    @classmethod
    def normalize_material_date(cls, value: datetime | str | None) -> datetime | None:
        return normalize_datetime_input(value)

    @field_validator("period_start", "period_end", mode="before")
    @classmethod
    def normalize_period_dt(cls, value: datetime | str | None) -> datetime | None:
        return normalize_datetime_input(value)

    @model_validator(mode="after")
    def require_customer(self) -> "CustomerMaterialBase":
        if self.customer_id is None:
            raise ValueError("customer_id is required")
        return self


class CustomerMaterialCreate(CustomerMaterialBase):
    pass


class CustomerMaterialUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    material_date: datetime | None = None
    status: CustomerMaterialStatusValue | None = None
    customer_id: int | None = None
    project_v2_id: int | None = None
    review_batch_id: int | None = None
    material_type: MaterialTypeValue | None = None
    period_start: datetime | None = None
    period_end: datetime | None = None
    raw_facts_markdown: str | None = None
    generation_meta: dict[str, Any] | None = None
    clear_project_v2: bool = False
    clear_batch: bool = False

    @field_validator("title", mode="before")
    @classmethod
    def normalize_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return normalize_required_text(value, field_name="title")

    @field_validator("material_date", mode="before")
    @classmethod
    def normalize_material_date(cls, value: datetime | str | None) -> datetime | None:
        return normalize_datetime_input(value)


class CustomerMaterialRead(BaseModel):
    id: int
    title: str
    material_date: datetime | None
    status: str
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None
    customer_id: int | None = None
    project_v2_id: int | None = None
    review_batch_id: int | None = None
    material_type: str | None = None
    period_start: datetime | None = None
    period_end: datetime | None = None
    raw_facts_markdown: str | None = None
    generation_meta: dict[str, Any] | None = None
