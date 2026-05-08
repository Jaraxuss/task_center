"""Fact V2 schemas and customer-material-fact link schemas."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from ._common import (
    FactSourceTypeValue,
    FactStatusValue,
    normalize_datetime_input,
    normalize_string_list,
)


class FactCreate(BaseModel):
    customer_id: int | None = None
    project_id: int | None = None
    task_id: int | None = None
    fact_date: datetime
    title: str = Field(..., min_length=1, max_length=255)
    raw_markdown: str = Field(..., min_length=1)
    source_type: FactSourceTypeValue = "manual_input"
    value_types: list[str] = Field(default_factory=list)
    status: FactStatusValue = "draft"

    @field_validator("title", mode="before")
    @classmethod
    def normalize_title(cls, v: str | None) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("title cannot be empty")
        return v

    @field_validator("raw_markdown", mode="before")
    @classmethod
    def normalize_raw(cls, v: str | None) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("raw_markdown cannot be empty")
        return v

    @field_validator("fact_date", mode="before")
    @classmethod
    def normalize_dt(cls, v: datetime | str | None) -> datetime:
        dt = normalize_datetime_input(v)
        if dt is None:
            raise ValueError("fact_date is required")
        return dt

    @field_validator("value_types", mode="before")
    @classmethod
    def normalize_vt(cls, v: list[str] | None) -> list[str]:
        return normalize_string_list(v)


class FactUpdate(BaseModel):
    customer_id: int | None = None
    project_id: int | None = None
    task_id: int | None = None
    fact_date: datetime | None = None
    title: str | None = Field(default=None, min_length=1, max_length=255)
    raw_markdown: str | None = None
    source_type: FactSourceTypeValue | None = None
    value_types: list[str] | None = None
    status: FactStatusValue | None = None
    clear_customer: bool = False
    clear_project: bool = False
    clear_task: bool = False

    @field_validator("fact_date", mode="before")
    @classmethod
    def normalize_dt(cls, v: datetime | str | None) -> datetime | None:
        return normalize_datetime_input(v)

    @field_validator("value_types", mode="before")
    @classmethod
    def normalize_vt(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        return normalize_string_list(v)


class FactRead(BaseModel):
    id: int
    customer_id: int | None
    project_id: int | None
    task_id: int | None
    fact_date: datetime
    title: str
    raw_markdown: str
    source_type: str
    value_types: list[str]
    status: str
    created_at: datetime
    updated_at: datetime


class CustomerMaterialFactRead(BaseModel):
    id: int
    material_id: int
    fact_id: int
    sort_order: int
    created_at: datetime


class CustomerMaterialFactCreate(BaseModel):
    fact_id: int
    sort_order: int = 0
