"""Knowledge module endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from db import get_db
from schemas import KnowledgeFactsOverview
from services.knowledge import build_facts_overview

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


@router.get("/facts/overview", response_model=KnowledgeFactsOverview)
def get_facts_overview(
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> KnowledgeFactsOverview:
    return build_facts_overview(db, status=status)
