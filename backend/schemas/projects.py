"""Project schemas (FK-based projects)."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from ._common import (
    ProjectStatusValue,
    ProjectTypeValue,
    normalize_datetime_input,
    normalize_project_name,
    normalize_string_list,
)


class ProjectCreate(BaseModel):
    customer_id: int | None = None
    project_type: ProjectTypeValue = "customer"
    name: str = Field(..., min_length=1, max_length=255)
    status: ProjectStatusValue = "active"
    area: str | None = Field(default=None, max_length=128)
    tags: list[str] = Field(default_factory=list)
    start_at: datetime | None = None
    target_end_at: datetime | None = None
    actual_end_at: datetime | None = None

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, v: str | None) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("name cannot be empty")
        return v

    @field_validator("area", mode="before")
    @classmethod
    def normalize_area(cls, v: str | None) -> str | None:
        return normalize_project_name(v)

    @field_validator("start_at", "target_end_at", "actual_end_at", mode="before")
    @classmethod
    def normalize_dt(cls, v: datetime | str | None) -> datetime | None:
        return normalize_datetime_input(v)

    @field_validator("tags", mode="before")
    @classmethod
    def normalize_tags(cls, v: list[str] | None) -> list[str]:
        return normalize_string_list(v)


class ProjectUpdate(BaseModel):
    customer_id: int | None = None
    project_type: ProjectTypeValue | None = None
    name: str | None = Field(default=None, min_length=1, max_length=255)
    status: ProjectStatusValue | None = None
    area: str | None = Field(default=None, max_length=128)
    tags: list[str] | None = None
    start_at: datetime | None = None
    target_end_at: datetime | None = None
    actual_end_at: datetime | None = None
    clear_customer: bool = False

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        if not v:
            raise ValueError("name cannot be empty")
        return v

    @field_validator("area", mode="before")
    @classmethod
    def normalize_area(cls, v: str | None) -> str | None:
        return normalize_project_name(v)

    @field_validator("start_at", "target_end_at", "actual_end_at", mode="before")
    @classmethod
    def normalize_dt(cls, v: datetime | str | None) -> datetime | None:
        return normalize_datetime_input(v)

    @field_validator("tags", mode="before")
    @classmethod
    def normalize_tags(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        return normalize_string_list(v)


class ProjectRead(BaseModel):
    id: int
    customer_id: int | None
    project_type: str
    name: str
    status: str
    area: str | None
    tags: list[str]
    start_at: datetime | None
    target_end_at: datetime | None
    actual_end_at: datetime | None
    created_at: datetime
    updated_at: datetime
