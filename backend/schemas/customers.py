"""Customer V2 schemas."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from ._common import CustomerStatusValue, normalize_project_name, normalize_string_list


class CustomerCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    key: str | None = Field(default=None, max_length=64)
    aliases: list[str] = Field(default_factory=list)
    status: CustomerStatusValue = "active"
    description: str | None = None
    area: str | None = Field(default=None, max_length=128)
    tags: list[str] = Field(default_factory=list)

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, v: str | None) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("name cannot be empty")
        return v

    @field_validator("key", mode="before")
    @classmethod
    def normalize_key(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        return v or None

    @field_validator("area", mode="before")
    @classmethod
    def normalize_area(cls, v: str | None) -> str | None:
        return normalize_project_name(v)

    @field_validator("aliases", "tags", mode="before")
    @classmethod
    def normalize_str_list(cls, v: list[str] | None) -> list[str]:
        return normalize_string_list(v)


class CustomerUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    key: str | None = Field(default=None, max_length=64)
    aliases: list[str] | None = None
    status: CustomerStatusValue | None = None
    description: str | None = None
    area: str | None = Field(default=None, max_length=128)
    tags: list[str] | None = None

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        if not v:
            raise ValueError("name cannot be empty")
        return v

    @field_validator("key", mode="before")
    @classmethod
    def normalize_key(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        return v or None

    @field_validator("area", mode="before")
    @classmethod
    def normalize_area(cls, v: str | None) -> str | None:
        return normalize_project_name(v)

    @field_validator("aliases", "tags", mode="before")
    @classmethod
    def normalize_str_list(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        return normalize_string_list(v)


class CustomerRead(BaseModel):
    id: int
    name: str
    key: str | None
    aliases: list[str]
    status: str
    description: str | None
    area: str | None
    tags: list[str]
    created_at: datetime
    updated_at: datetime
