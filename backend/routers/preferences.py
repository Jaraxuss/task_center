"""Board preference endpoints."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from db import get_db
from schemas import BoardPreferenceRead, BoardPreferenceUpdate, KnowledgePreferenceRead, KnowledgePreferenceUpdate
from services.board import get_board_preference, serialize_board_preference
from services.knowledge import get_knowledge_preference, serialize_knowledge_preference

router = APIRouter(prefix="/api/preferences", tags=["preferences"])


@router.get("/board", response_model=BoardPreferenceRead)
def get_board_preferences(db: Session = Depends(get_db)) -> BoardPreferenceRead:
    return serialize_board_preference(get_board_preference(db))


@router.patch("/board", response_model=BoardPreferenceRead)
def update_board_preferences(
    payload: BoardPreferenceUpdate, db: Session = Depends(get_db)
) -> BoardPreferenceRead:
    preference = get_board_preference(db)
    updates = payload.model_dump(exclude_unset=True)

    if "task_order" in updates and updates["task_order"] is not None:
        preference.task_order_json = json.dumps(updates["task_order"], ensure_ascii=False)
    if "pinned_projects" in updates and updates["pinned_projects"] is not None:
        preference.pinned_projects_json = json.dumps(updates["pinned_projects"], ensure_ascii=False)
    if "project_order" in updates and updates["project_order"] is not None:
        preference.project_order_json = json.dumps(updates["project_order"], ensure_ascii=False)

    db.add(preference)
    db.commit()
    db.refresh(preference)
    return serialize_board_preference(preference)


@router.get("/knowledge", response_model=KnowledgePreferenceRead)
def get_knowledge_preferences(db: Session = Depends(get_db)) -> KnowledgePreferenceRead:
    return serialize_knowledge_preference(get_knowledge_preference(db))


@router.patch("/knowledge", response_model=KnowledgePreferenceRead)
def update_knowledge_preferences(
    payload: KnowledgePreferenceUpdate, db: Session = Depends(get_db)
) -> KnowledgePreferenceRead:
    pref = get_knowledge_preference(db)
    updates = payload.model_dump(exclude_unset=True)

    if "pinned_customer_ids" in updates and updates["pinned_customer_ids"] is not None:
        pref.pinned_customer_ids_json = json.dumps(updates["pinned_customer_ids"], ensure_ascii=False)
    if "customer_order_ids" in updates and updates["customer_order_ids"] is not None:
        pref.customer_order_ids_json = json.dumps(updates["customer_order_ids"], ensure_ascii=False)

    db.add(pref)
    db.commit()
    db.refresh(pref)
    return serialize_knowledge_preference(pref)
