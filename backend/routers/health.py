"""Health and nightly-review placeholder endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db import DATABASE_PATH as DB_PATH
from db import get_db
from models import Task, TaskStatus
from schemas import HealthResponse, NightlyReviewPlaceholder
from timeutils import now_local

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", db=str(DB_PATH), now=now_local())


@router.get("/nightly-review", response_model=NightlyReviewPlaceholder)
def nightly_review_placeholder(db: Session = Depends(get_db)) -> NightlyReviewPlaceholder:
    pending_count = db.scalar(
        select(func.count(Task.id)).where(
            Task.status.in_([TaskStatus.TODO.value, TaskStatus.DOING.value, TaskStatus.DEFERRED.value])
        )
    ) or 0
    return NightlyReviewPlaceholder(
        note="22:00 晚间收口流程暂未实现自动执行，但已保留 nightly_bucket/nightly_reviewed_at 与 nightly_reviewed 事件类型供后续 cron/聊天指令接入。重复任务已支持 recurrence 配置与下一次触发时间计算。",
        pending_candidates=pending_count,
    )
