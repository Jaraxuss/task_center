"""Task API smoke tests.

Goal: lock the current observable behaviour of /api/tasks (create, update,
complete, defer, cancel, recurrence advancing) so that the Phase 1 refactor
can be verified to be behaviour-preserving.

These tests run against the isolated temp DB managed by ``conftest.py``.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from timeutils import APP_TIMEZONE


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _create_task(client: TestClient, **overrides) -> dict:
    payload = {
        "title": "示例任务",
        "description": "smoke test",
        "due_at": _iso(datetime.now(timezone.utc) + timedelta(hours=4)),
        "project": "测试项目",
        "tags": ["smoke"],
        "source": "test",
        "reminders": [],
    }
    payload.update(overrides)
    response = client.post("/api/tasks", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


# --- Health & list ---------------------------------------------------------


def test_health_endpoint(api_client: TestClient) -> None:
    response = api_client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    # The ``db`` field should reference the temp test DB, never production.
    assert "task_center_test" in body["db"], body["db"]


def test_list_tasks_empty_initially(api_client: TestClient) -> None:
    response = api_client.get("/api/tasks")
    assert response.status_code == 200
    assert response.json() == []


# --- Create ----------------------------------------------------------------


def test_create_task_returns_detail_with_event(api_client: TestClient) -> None:
    body = _create_task(api_client)
    assert body["id"] > 0
    assert body["title"] == "示例任务"
    assert body["status"] == "todo"
    assert body["tags"] == ["smoke"]
    assert any(event["event_type"] == "created" for event in body["events"])


# --- Complete (non-recurring) ---------------------------------------------


def test_complete_task_marks_done_and_emits_event(api_client: TestClient) -> None:
    created = _create_task(api_client)
    response = api_client.post(
        f"/api/tasks/{created['id']}/complete",
        json={"note": "搞定"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "done"
    assert body["completion_note"] == "搞定"
    assert body["completed_at"] is not None
    event_types = [event["event_type"] for event in body["events"]]
    assert "completed" in event_types
    assert "status_changed" in event_types


# --- Defer -----------------------------------------------------------------


def test_defer_task_sets_deferred_status_and_dates(api_client: TestClient) -> None:
    created = _create_task(api_client)
    deferred_to = datetime.now(timezone.utc) + timedelta(days=2)
    response = api_client.post(
        f"/api/tasks/{created['id']}/defer",
        json={"deferred_to": _iso(deferred_to), "reason": "等回复"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "deferred"
    assert body["deferred_to"] is not None
    # ``due_at`` is realigned to ``deferred_to`` when ``due_at`` not specified.
    assert body["due_at"] == body["deferred_to"]


# --- Cancel ----------------------------------------------------------------


def test_cancel_task_marks_canceled(api_client: TestClient) -> None:
    created = _create_task(api_client)
    response = api_client.post(
        f"/api/tasks/{created['id']}/cancel",
        json={"reason": "需求取消"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "canceled"
    assert body["canceled_at"] is not None


# --- Update ---------------------------------------------------------------


def test_update_task_changes_title_and_records_event(api_client: TestClient) -> None:
    created = _create_task(api_client)
    response = api_client.patch(
        f"/api/tasks/{created['id']}",
        json={"title": "新的标题"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["title"] == "新的标题"
    assert any(event["event_type"] == "updated" for event in body["events"])


# --- Recurrence: completing advances to next run --------------------------


def test_completing_recurring_task_advances_next_run(api_client: TestClient) -> None:
    """Critical behavioural contract: completing a recurring task should NOT
    mark it done permanently; it should advance ``due_at`` to the next run
    and set status back to ``todo``.

    Note: ``upsert_recurrence`` runs at task-creation time and may overwrite
    a user-provided ``due_at`` with the recurrence engine's next-run-from-now
    if the user supplied a past anchor. To stay deterministic regardless of
    wall clock, we anchor 7 days into the future and read the canonical
    ``due_at`` back from the create response.
    """

    # 7 days from "today" at noon SH gives the recurrence engine a clean anchor.
    today_sh = datetime.now(APP_TIMEZONE).replace(hour=12, minute=0, second=0, microsecond=0)
    anchor_local = today_sh + timedelta(days=7)
    created = _create_task(
        api_client,
        title="每日复盘",
        due_at=_iso(anchor_local),
        recurrence={
            "enabled": True,
            "frequency": "daily",
            "interval": 1,
            "timezone": "Asia/Shanghai",
            "time_of_day": "12:00",
            "days_of_week": [],
            "day_of_month": None,
            "start_at": _iso(anchor_local),
            "end_at": None,
            "reminder_offsets_minutes": [],
        },
    )
    assert created["recurrence"] is not None
    assert created["recurrence"]["frequency"] == "daily"

    # Read the canonical anchor back; it should be exactly what we posted.
    anchor_from_server = datetime.fromisoformat(created["due_at"].replace("Z", "+00:00")).astimezone(APP_TIMEZONE)
    assert anchor_from_server == anchor_local

    # Complete 30 minutes past the scheduled run.
    completed_at = anchor_from_server + timedelta(minutes=30)
    response = api_client.post(
        f"/api/tasks/{created['id']}/complete",
        json={"completed_at": _iso(completed_at), "note": "done"},
    )
    assert response.status_code == 200, response.text
    body = response.json()

    # Status should have rolled back to todo (next run not yet completed).
    assert body["status"] == "todo"
    assert body["completed_at"] is None
    # New due_at should be exactly one day after the original anchor.
    next_due_local = datetime.fromisoformat(body["due_at"].replace("Z", "+00:00")).astimezone(APP_TIMEZONE)
    assert next_due_local == anchor_local + timedelta(days=1)
    # Recurrence event should be present.
    event_types = [event["event_type"] for event in body["events"]]
    assert "recurrence_advanced" in event_types


# --- 404 handling ---------------------------------------------------------


def test_get_task_returns_404_for_unknown_id(api_client: TestClient) -> None:
    response = api_client.get("/api/tasks/999999")
    assert response.status_code == 404


def test_complete_unknown_task_returns_404(api_client: TestClient) -> None:
    response = api_client.post("/api/tasks/999999/complete", json={})
    assert response.status_code == 404


# --- Dashboard contracts --------------------------------------------------


def test_dashboard_today_returns_summary_shape(api_client: TestClient) -> None:
    _create_task(api_client, title="今日 A")
    response = api_client.get("/api/dashboard/today")
    assert response.status_code == 200
    body = response.json()
    # Field presence (locks current contract for both frontends).
    for key in ("date", "tasks", "total", "open_count", "completed_count", "plan_groups"):
        assert key in body, f"missing field {key}"


def test_dashboard_board_returns_grouped_statuses(api_client: TestClient) -> None:
    _create_task(api_client, title="任务")
    response = api_client.get("/api/dashboard/board")
    assert response.status_code == 200
    body = response.json()
    statuses = {group["status"] for group in body["groups"]}
    # All five canonical statuses always present (even if empty).
    assert {"todo", "doing", "deferred", "done", "canceled"}.issubset(statuses)
