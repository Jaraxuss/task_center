"""Board preference endpoints."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from db import get_db
from schemas import BoardPreferenceRead, BoardPreferenceUpdate
from services.board import get_board_preference, serialize_board_preference

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
