from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from config import Settings
from db import SessionLocal
from models import Reminder, ReminderStatus, Task
from services.openclaw_cron import parse_cron_job_id
from services.reminder_worker import process_due_card_reminders


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _create_task(client: TestClient, **overrides) -> dict:
    payload = {
        "title": "提醒测试任务",
        "description": "提醒测试备注",
        "due_at": _iso(datetime.now(timezone.utc) + timedelta(hours=1)),
        "source": "test",
        "reminders": [],
    }
    payload.update(overrides)
    response = client.post("/api/tasks", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _settings() -> Settings:
    return Settings(
        api_host="0.0.0.0",
        api_port=8000,
        cors_origins=[],
        database_path=Path(str(SessionLocal.kw["bind"].url.database)),  # type: ignore[arg-type]
        database_url=str(SessionLocal.kw["bind"].url),  # type: ignore[arg-type]
        feishu_app_id="cli_test",
        feishu_app_secret="secret",
        feishu_default_receive_id="ou_default",
        feishu_default_receive_id_type="open_id",
        reminder_worker_interval_seconds=30,
        reminder_max_retries=2,
    )


@dataclass
class FakeDeliveryResult:
    provider: str = "feishu_card_v2"
    status: str = "sent"
    task_id: int = 1
    receive_id_type: str = "open_id"
    message_id: str | None = "om_test"
    request_uuid: str | None = "tc-reminder-1"
    card: dict[str, Any] | None = None
    card_size_bytes: int = 123
    raw_response: dict[str, Any] | None = None


def test_null_delivery_mode_falls_back_to_v2_worker(api_client: TestClient) -> None:
    created = _create_task(
        api_client,
        reminders=[{"remind_at": _iso(datetime.now(timezone.utc) - timedelta(seconds=1)), "note": "到点"}],
    )
    modes: list[str | None] = []

    def fake_sender(reminder: Reminder, **_: Any) -> FakeDeliveryResult:
        modes.append(reminder.delivery_mode)
        return FakeDeliveryResult(task_id=reminder.task_id, request_uuid=reminder.request_uuid)

    with SessionLocal() as session:
        result = process_due_card_reminders(session, settings=_settings(), sender=fake_sender)

    assert result.processed == 1
    assert result.fired == 1
    assert modes == [None]

    refreshed = api_client.get(f"/api/tasks/{created['id']}").json()
    reminder = refreshed["reminders"][0]
    assert reminder["status"] == "fired"
    assert reminder["message_id"] == "om_test"
    assert reminder["request_uuid"] == f"tc-reminder-{reminder['id']}"


def test_v1_delivery_mode_is_processed_by_worker(api_client: TestClient) -> None:
    _create_task(
        api_client,
        reminders=[
            {
                "remind_at": _iso(datetime.now(timezone.utc) - timedelta(seconds=1)),
                "delivery_mode": "feishu_card_v1",
            }
        ],
    )
    modes: list[str | None] = []

    def fake_sender(reminder: Reminder, **_: Any) -> FakeDeliveryResult:
        modes.append(reminder.delivery_mode)
        return FakeDeliveryResult(provider="feishu_card_v1", task_id=reminder.task_id, request_uuid=reminder.request_uuid)

    with SessionLocal() as session:
        result = process_due_card_reminders(session, settings=_settings(), sender=fake_sender)

    assert result.fired == 1
    assert modes == ["feishu_card_v1"]


def test_worker_marks_failed_after_max_retries(api_client: TestClient) -> None:
    _create_task(
        api_client,
        reminders=[{"remind_at": _iso(datetime.now(timezone.utc) - timedelta(seconds=1))}],
    )

    def failing_sender(reminder: Reminder, **_: Any) -> FakeDeliveryResult:
        raise RuntimeError("boom")

    with SessionLocal() as session:
        first = process_due_card_reminders(session, settings=_settings(), sender=failing_sender)
        second = process_due_card_reminders(session, settings=_settings(), sender=failing_sender)

    assert first.retried == 1
    assert second.failed == 1


def test_ai_reminder_create_calls_openclaw_cron(monkeypatch, api_client: TestClient) -> None:
    calls: list[tuple[int, int]] = []

    def fake_create(reminder: Reminder, task: Task):
        calls.append((reminder.id, task.id))

        class Result:
            job_id = "job_ai_1"

        return Result()

    monkeypatch.setattr("routers.tasks.create_ai_reminder_job", fake_create)

    created = _create_task(api_client)
    response = api_client.post(
        f"/api/tasks/{created['id']}/reminders",
        json={
            "remind_at": _iso(datetime.now(timezone.utc) + timedelta(hours=1)),
            "delivery_mode": "openclaw_cron_agent",
            "receive_id": "ou_test",
            "receive_id_type": "open_id",
            "ai_prompt": "提醒我处理这件事",
        },
    )

    assert response.status_code == 201, response.text
    body = response.json()
    reminder = body["reminders"][0]
    assert reminder["external_cron_job_id"] == "job_ai_1"
    assert calls == [(reminder["id"], created["id"])]


def test_switch_ai_reminder_to_v2_removes_cron(monkeypatch, api_client: TestClient) -> None:
    removed: list[str] = []

    def fake_create(reminder: Reminder, task: Task):
        class Result:
            job_id = "job_ai_1"

        return Result()

    def fake_remove(job_id: str):
        removed.append(job_id)

        class Result:
            pass

        return Result()

    monkeypatch.setattr("routers.tasks.create_ai_reminder_job", fake_create)
    monkeypatch.setattr("routers.tasks.remove_ai_reminder_job", fake_remove)

    created = _create_task(api_client)
    created = api_client.post(
        f"/api/tasks/{created['id']}/reminders",
        json={
            "remind_at": _iso(datetime.now(timezone.utc) + timedelta(hours=1)),
            "delivery_mode": "openclaw_cron_agent",
            "receive_id": "ou_test",
            "ai_prompt": "AI prompt",
        },
    ).json()
    reminder_id = created["reminders"][0]["id"]

    response = api_client.patch(
        f"/api/tasks/{created['id']}/reminders/{reminder_id}",
        json={"delivery_mode": "feishu_card_v2"},
    )

    assert response.status_code == 200, response.text
    assert removed == ["job_ai_1"]
    assert response.json()["reminders"][0]["external_cron_job_id"] is None


def test_cancel_task_removes_pending_ai_cron(monkeypatch, api_client: TestClient) -> None:
    removed: list[str] = []

    def fake_create(reminder: Reminder, task: Task):
        class Result:
            job_id = "job_ai_1"

        return Result()

    def fake_remove(job_id: str):
        removed.append(job_id)

        class Result:
            pass

        return Result()

    monkeypatch.setattr("routers.tasks.create_ai_reminder_job", fake_create)
    monkeypatch.setattr("routers.tasks.remove_ai_reminder_job", fake_remove)

    created = _create_task(
        api_client,
        reminders=[
            {
                "remind_at": _iso(datetime.now(timezone.utc) + timedelta(hours=1)),
                "delivery_mode": "openclaw_cron_agent",
                "receive_id": "ou_test",
                "ai_prompt": "AI prompt",
            }
        ],
    )

    response = api_client.post(f"/api/tasks/{created['id']}/cancel", json={"reason": "取消"})

    assert response.status_code == 200, response.text
    assert removed == ["job_ai_1"]
    assert response.json()["reminders"][0]["status"] == ReminderStatus.CANCELED.value


def test_parse_cron_job_id_best_effort() -> None:
    assert parse_cron_job_id("created job: abc123") == "abc123"
    assert parse_cron_job_id("id=job-1") == "job-1"
    assert parse_cron_job_id("no stable id yet") is None
