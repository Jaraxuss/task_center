from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import Settings
from models import Project, Task
from services.notification_delivery import reminder_target, send_task_card_v1, send_task_card_v2, task_card_request_uuid
from services.task_card_builder import build_task_card_v1, build_task_card_v2, task_card_markdown


def _settings() -> Settings:
    return Settings(
        api_host="0.0.0.0",
        api_port=8000,
        cors_origins=[],
        database_path=Path(":memory:"),
        database_url="sqlite:///:memory:",
        feishu_app_id="cli_test",
        feishu_app_secret="secret",
        feishu_default_receive_id="ou_example_user",
        feishu_default_receive_id_type="open_id",
    )


def _task() -> Task:
    task = Task(
        id=156,
        title="让朱老师填写私有云部署前信息问卷",
        description="Acme Corp私有云部署申请已提交；下一步需要引导客户朱老师填写部署前信息问卷。",
        due_at=datetime(2026, 5, 19, 11, 30, tzinfo=timezone.utc),
        status="todo",
        area="上海",
        source="test",
    )
    task.updated_at = datetime(2026, 5, 19, 1, 2, 3, tzinfo=timezone.utc)
    task.project_rel = Project(id=1, name="Acme Corp")
    return task


def _reminder(receive_id: str | None = None):
    from models import Reminder

    return Reminder(task_id=156, remind_at=datetime(2026, 5, 19, 1, 0, tzinfo=timezone.utc), receive_id=receive_id)


class FakeCardSender:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def send_card(
        self,
        *,
        receive_id: str,
        card: dict[str, Any],
        receive_id_type: str = "open_id",
        uuid: str | None = None,
    ) -> dict[str, Any]:
        self.calls.append(
            {
                "receive_id": receive_id,
                "receive_id_type": receive_id_type,
                "card": card,
                "uuid": uuid,
            }
        )
        return {"code": 0, "msg": "success", "data": {"message_id": "om_test"}}


def test_task_card_markdown_contains_task_context() -> None:
    markdown = task_card_markdown(_task(), note="请今天处理")

    assert "task_center #156" in markdown
    assert "让朱老师填写私有云部署前信息问卷" in markdown
    assert "2026-05-19 19:30" in markdown
    assert "Acme Corp" in markdown
    assert "请今天处理" in markdown


def test_build_task_card_v2_returns_feishu_card() -> None:
    card = build_task_card_v2(_task())

    assert card["schema"] == "2.0"
    assert card["header"]["title"]["content"] == "TaskCenter 提醒"
    assert card["header"]["subtitle"]["content"] == "task_center #156"
    assert "task_center #156" in card["body"]["elements"][0]["content"]


def test_build_task_card_v1_returns_fallback_feishu_card() -> None:
    card = build_task_card_v1(_task())

    assert "schema" not in card
    assert card["header"]["title"]["content"] == "TaskCenter 提醒"
    assert card["header"]["subtitle"]["content"] == "task_center #156"
    assert "task_center #156" in card["elements"][0]["content"]


def test_send_task_card_v2_dry_run_does_not_send() -> None:
    sender = FakeCardSender()
    result = send_task_card_v2(_task(), dry_run=True, settings=_settings(), client=sender)

    assert result.status == "dry_run"
    assert result.provider == "feishu_card_v2"
    assert result.message_id is None
    assert result.receive_id_type == "open_id"
    assert result.card_size_bytes > 0
    assert sender.calls == []


def test_send_task_card_v2_sends_to_configured_open_id() -> None:
    sender = FakeCardSender()
    task = _task()
    result = send_task_card_v2(task, note="移动端手动触发", settings=_settings(), client=sender)

    assert result.status == "sent"
    assert result.message_id == "om_test"
    assert result.request_uuid == task_card_request_uuid(task)
    assert len(sender.calls) == 1
    call = sender.calls[0]
    assert call["receive_id"] == "ou_example_user"
    assert call["receive_id_type"] == "open_id"
    assert call["uuid"] == task_card_request_uuid(task)
    assert "移动端手动触发" in call["card"]["body"]["elements"][0]["content"]


def test_send_task_card_v1_sends_to_configured_open_id() -> None:
    sender = FakeCardSender()
    task = _task()
    result = send_task_card_v1(task, note="兼容模式", settings=_settings(), client=sender)

    assert result.status == "sent"
    assert result.provider == "feishu_card_v1"
    assert result.message_id == "om_test"
    call = sender.calls[0]
    assert call["receive_id"] == "ou_example_user"
    assert call["receive_id_type"] == "open_id"
    assert "兼容模式" in call["card"]["elements"][0]["content"]


def test_reminder_target_uses_per_reminder_receive_id_without_default() -> None:
    settings = _settings()
    settings = Settings(**{**settings.__dict__, "feishu_default_receive_id": None})

    assert reminder_target(_reminder("ou_custom"), settings) == ("ou_custom", "open_id")


def test_reminder_target_requires_receive_id_when_no_default() -> None:
    settings = _settings()
    settings = Settings(**{**settings.__dict__, "feishu_default_receive_id": None})

    try:
        reminder_target(_reminder(), settings)
    except ValueError as exc:
        assert "Reminder receive_id is required" in str(exc)
    else:
        raise AssertionError("expected ValueError")
