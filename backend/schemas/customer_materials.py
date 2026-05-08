"""Customer-material schemas (legacy + V2 fields consolidated)."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from ._common import (
    CustomerMaterialStatusValue,
    MaterialTypeValue,
    normalize_datetime_input,
    normalize_project_name,
    normalize_required_text,
    normalize_string_list,
)


class CustomerMaterialBase(BaseModel):
    project: str | None = Field(default=None, max_length=128)
    title: str = Field(..., min_length=1, max_length=255)
    material_date: datetime | None = None
    source_type: str = Field(default="text", max_length=32)
    source: str = Field(default="chat", max_length=32)
    source_refs: dict[str, Any] = Field(default_factory=dict)
    value_types: list[str] = Field(default_factory=list)
    status: CustomerMaterialStatusValue = "pending"
    task_id: int | None = None
    # V2 fields (consolidated into main schema per API consolidation plan)
    customer_id: int | None = None
    project_v2_id: int | None = None
    review_batch_id: int | None = None
    material_type: MaterialTypeValue = "period_summary"
    period_start: datetime | None = None
    period_end: datetime | None = None
    raw_facts_markdown: str | None = None
    generation_meta: dict[str, Any] | None = None

    @field_validator("project", mode="before")
    @classmethod
    def normalize_material_project(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = normalize_project_name(value)
        if not normalized:
            raise ValueError("project cannot be empty")
        return normalized

    @field_validator("title", mode="before")
    @classmethod
    def normalize_title(cls, value: str | None) -> str:
        return normalize_required_text(value, field_name="title")

    @field_validator("source_type", mode="before")
    @classmethod
    def normalize_source_type(cls, value: str | None) -> str:
        return (value or "").strip() or "text"

    @field_validator("source", mode="before")
    @classmethod
    def normalize_source(cls, value: str | None) -> str:
        return (value or "").strip() or "chat"

    @field_validator("material_date", mode="before")
    @classmethod
    def normalize_material_date(cls, value: datetime | str | None) -> datetime | None:
        return normalize_datetime_input(value)

    @field_validator("value_types", mode="before")
    @classmethod
    def normalize_value_types(cls, value: list[str] | None) -> list[str]:
        return normalize_string_list(value)

    @field_validator("period_start", "period_end", mode="before")
    @classmethod
    def normalize_period_dt(cls, value: datetime | str | None) -> datetime | None:
        return normalize_datetime_input(value)

    @model_validator(mode="after")
    def require_legacy_project_or_customer(self) -> "CustomerMaterialBase":
        if self.project is None and self.customer_id is None:
            raise ValueError("project or customer_id is required")
        return self


class CustomerMaterialCreate(CustomerMaterialBase):
    pass


class CustomerMaterialUpdate(BaseModel):
    project: str | None = Field(default=None, max_length=128)
    title: str | None = Field(default=None, min_length=1, max_length=255)
    material_date: datetime | None = None
    source_type: str | None = Field(default=None, max_length=32)
    source: str | None = Field(default=None, max_length=32)
    source_refs: dict[str, Any] | None = None
    value_types: list[str] | None = None
    status: CustomerMaterialStatusValue | None = None
    task_id: int | None = None
    clear_task: bool = False
    # V2 fields
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

    @field_validator("project", mode="before")
    @classmethod
    def normalize_material_project(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = normalize_project_name(value)
        if not normalized:
            raise ValueError("project cannot be empty")
        return normalized

    @field_validator("title", mode="before")
    @classmethod
    def normalize_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return normalize_required_text(value, field_name="title")

    @field_validator("source_type", "source", mode="before")
    @classmethod
    def normalize_optional_short_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None

    @field_validator("material_date", mode="before")
    @classmethod
    def normalize_material_date(cls, value: datetime | str | None) -> datetime | None:
        return normalize_datetime_input(value)

    @field_validator("value_types", mode="before")
    @classmethod
    def normalize_value_types(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        return normalize_string_list(value)


class CustomerMaterialRead(BaseModel):
    id: int
    project: str | None
    title: str
    material_date: datetime | None
    source_type: str
    source: str
    source_refs: dict[str, Any]
    value_types: list[str]
    status: str
    task_id: int | None
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None
    # V2 fields
    customer_id: int | None = None
    project_v2_id: int | None = None
    review_batch_id: int | None = None
    material_type: str | None = None
    period_start: datetime | None = None
    period_end: datetime | None = None
    raw_facts_markdown: str | None = None
    generation_meta: dict[str, Any] | None = None
