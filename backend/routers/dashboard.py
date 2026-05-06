"""Dashboard endpoints (today / plan / board / history / aggregate)."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from db import get_db
from schemas import (
    BoardSummary,
    DashboardPayload,
    HistorySummary,
    PlanSummary,
    TodaySummary,
)
from services.dashboard import (
    build_board_summary,
    build_history_summary,
    build_plan_summary,
    build_today_summary,
)

router = APIRouter(prefix="/api", tags=["dashboard"])


@router.get("/history", response_model=HistorySummary)
def history(
    date_value: date | None = Query(default=None, alias="date"),
    status: str | None = Query(default=None),
    q: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> HistorySummary:
    return build_history_summary(db, target=date_value, status=status, query=q)


@router.get("/dashboard/today", response_model=TodaySummary)
def dashboard_today(db: Session = Depends(get_db)) -> TodaySummary:
    return build_today_summary(db)


@router.get("/dashboard/plan", response_model=PlanSummary)
def dashboard_plan(db: Session = Depends(get_db)) -> PlanSummary:
    return build_plan_summary(db)


@router.get("/dashboard/board", response_model=BoardSummary)
def dashboard_board(db: Session = Depends(get_db)) -> BoardSummary:
    return build_board_summary(db)


@router.get("/dashboard/history", response_model=HistorySummary)
def dashboard_history(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> HistorySummary:
    summary = build_history_summary(db)
    summary.tasks = summary.tasks[:limit]
    summary.total = len(summary.tasks)
    return summary


@router.get("/dashboard", response_model=DashboardPayload)
def dashboard(db: Session = Depends(get_db)) -> DashboardPayload:
    return DashboardPayload(
        today=build_today_summary(db),
        board=build_board_summary(db),
        history=build_history_summary(db),
    )
