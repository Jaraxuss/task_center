"""Review batch schemas."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from ._common import ReviewBatchStatusValue, ReviewBatchTypeValue, normalize_datetime_input


class ReviewBatchCreate(BaseModel):
    batch_type: ReviewBatchTypeValue = "weekly_customer_summary"
    title: str = Field(..., min_length=1, max_length=255)
    period_start: datetime | None = None
    period_end: datetime | None = None
    status: ReviewBatchStatusValue = "pending"
    material_count: int = 0
    created_by: str = "manual"

    @field_validator("title", mode="before")
    @classmethod
    def normalize_title(cls, v: str | None) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("title cannot be empty")
        return v

    @field_validator("period_start", "period_end", mode="before")
    @classmethod
    def normalize_dt(cls, v: datetime | str | None) -> datetime | None:
        return normalize_datetime_input(v)


class ReviewBatchUpdate(BaseModel):
    batch_type: ReviewBatchTypeValue | None = None
    title: str | None = Field(default=None, min_length=1, max_length=255)
    period_start: datetime | None = None
    period_end: datetime | None = None
    status: ReviewBatchStatusValue | None = None
    material_count: int | None = None
    created_by: str | None = None

    @field_validator("title", mode="before")
    @classmethod
    def normalize_title(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        if not v:
            raise ValueError("title cannot be empty")
        return v

    @field_validator("period_start", "period_end", mode="before")
    @classmethod
    def normalize_dt(cls, v: datetime | str | None) -> datetime | None:
        return normalize_datetime_input(v)


class ReviewBatchRead(BaseModel):
    id: int
    batch_type: str
    title: str
    period_start: datetime | None
    period_end: datetime | None
    status: str
    material_count: int
    created_by: str
    created_at: datetime
    updated_at: datetime
