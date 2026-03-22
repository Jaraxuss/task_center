from __future__ import annotations

import os
from dataclasses import dataclass


DEFAULT_CORS_ORIGINS = [
    "http://127.0.0.1:5173",
    "http://localhost:5173",
]


@dataclass(frozen=True)
class Settings:
    api_host: str
    api_port: int
    cors_origins: list[str]


def _split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip().rstrip("/") for item in value.split(",") if item.strip()]


def get_settings() -> Settings:
    api_host = os.getenv("TASK_CENTER_API_HOST", "0.0.0.0").strip() or "0.0.0.0"
    api_port = int(os.getenv("TASK_CENTER_API_PORT", "8000"))
    cors_origins = _split_csv(os.getenv("TASK_CENTER_CORS_ORIGINS")) or DEFAULT_CORS_ORIGINS
    return Settings(api_host=api_host, api_port=api_port, cors_origins=cors_origins)
