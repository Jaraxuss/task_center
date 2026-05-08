"""Shared HTTP/DB helper utilities used by routers and other services.

Phase 1.B §8.2: collect a small set of well-trodden patterns that were
previously inlined in every router. Keep this module deliberately tiny —
overgeneralizing tends to obscure rather than help.
"""
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from db import Base


def get_or_404[T: Base](db: Session, model: type[T], entity_id: int, *, name: str | None = None) -> T:
    """Fetch ``model`` by primary key or raise HTTP 404.

    The 404 ``detail`` defaults to ``"<Model> not found"``; pass ``name`` to
    override (e.g. ``name="Task"`` to keep wording stable when the model is
    renamed). Returns the entity untouched.
    """
    entity = db.get(model, entity_id)
    if entity is None:
        label = name or model.__name__
        raise HTTPException(status_code=404, detail=f"{label} not found")
    return entity
