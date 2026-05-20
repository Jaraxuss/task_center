"""Notification delivery services for TaskCenter."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from config import Settings, get_settings
from models import Reminder, ReminderDeliveryMode, Task
from services.feishu_card import FeishuCardClient, FeishuTarget, serialized_card_size
from services.feishu_card_v1 import FeishuCardV1Client
from services.feishu_card_v1 import FeishuTarget as FeishuTargetV1
from services.feishu_card_v1 import serialized_card_size as serialized_card_v1_size
from services.task_card_builder import build_task_card_v1, build_task_card_v2


class CardSender(Protocol):
    def send_card(
        self,
        *,
        receive_id: str,
        card: dict[str, Any],
        receive_id_type: str = "open_id",
        uuid: str | None = None,
    ) -> dict[str, Any]: ...


@dataclass(frozen=True)
class TaskCardDeliveryResult:
    provider: str
    status: str
    task_id: int
    receive_id_type: str
    message_id: str | None
    request_uuid: str | None
    card: dict[str, Any]
    card_size_bytes: int
    raw_response: dict[str, Any] | None = None


def task_card_request_uuid(task: Task) -> str:
    """Build a deterministic UUID for manual task-card delivery attempts."""

    updated_at = int(task.updated_at.timestamp()) if task.updated_at else 0
    return f"tc-task-{task.id}-{updated_at}"


def reminder_request_uuid(reminder: Reminder) -> str:
    return f"tc-reminder-{reminder.id}"


def reminder_delivery_mode(reminder: Reminder) -> str:
    return reminder.delivery_mode or ReminderDeliveryMode.FEISHU_CARD_V2.value


def reminder_target(
    reminder: Reminder, settings: Settings
) -> tuple[str, str]:
    if reminder.receive_id:
        return (reminder.receive_id, reminder.receive_id_type or "open_id")
    default_target = FeishuTarget.from_settings(settings)
    return (
        default_target.receive_id,
        default_target.receive_id_type,
    )


def send_task_card_v2(
    task: Task,
    *,
    note: str | None = None,
    dry_run: bool = False,
    request_uuid: str | None = None,
    settings: Settings | None = None,
    client: CardSender | None = None,
) -> TaskCardDeliveryResult:
    """Build and optionally send a TaskCenter task card through Feishu V2."""

    resolved_settings = settings or get_settings()
    target = FeishuTarget.from_settings(resolved_settings)
    card = build_task_card_v2(task, note=note)
    size = serialized_card_size(card)
    resolved_uuid = request_uuid or task_card_request_uuid(task)

    if dry_run:
        return TaskCardDeliveryResult(
            provider="feishu_card_v2",
            status="dry_run",
            task_id=task.id,
            receive_id_type=target.receive_id_type,
            message_id=None,
            request_uuid=resolved_uuid,
            card=card,
            card_size_bytes=size.bytes,
            raw_response=None,
        )

    sender = client or FeishuCardClient.from_settings(resolved_settings)
    response = sender.send_card(
        receive_id=target.receive_id,
        receive_id_type=target.receive_id_type,
        card=card,
        uuid=resolved_uuid,
    )
    message_id = response.get("data", {}).get("message_id") if isinstance(response.get("data"), dict) else None
    return TaskCardDeliveryResult(
        provider="feishu_card_v2",
        status="sent",
        task_id=task.id,
        receive_id_type=target.receive_id_type,
        message_id=str(message_id) if message_id else None,
        request_uuid=resolved_uuid,
        card=card,
        card_size_bytes=size.bytes,
        raw_response=response,
    )


def send_task_card_v1(
    task: Task,
    *,
    note: str | None = None,
    dry_run: bool = False,
    request_uuid: str | None = None,
    settings: Settings | None = None,
    client: CardSender | None = None,
) -> TaskCardDeliveryResult:
    """Build and optionally send a TaskCenter task card through Feishu V1."""

    resolved_settings = settings or get_settings()
    target = FeishuTargetV1.from_settings(resolved_settings)
    card = build_task_card_v1(task, note=note)
    size = serialized_card_v1_size(card)
    resolved_uuid = request_uuid or task_card_request_uuid(task)

    if dry_run:
        return TaskCardDeliveryResult(
            provider="feishu_card_v1",
            status="dry_run",
            task_id=task.id,
            receive_id_type=target.receive_id_type,
            message_id=None,
            request_uuid=resolved_uuid,
            card=card,
            card_size_bytes=size.bytes,
            raw_response=None,
        )

    sender = client or FeishuCardV1Client.from_settings(resolved_settings)
    response = sender.send_card(
        receive_id=target.receive_id,
        receive_id_type=target.receive_id_type,
        card=card,
        uuid=resolved_uuid,
    )
    message_id = response.get("data", {}).get("message_id") if isinstance(response.get("data"), dict) else None
    return TaskCardDeliveryResult(
        provider="feishu_card_v1",
        status="sent",
        task_id=task.id,
        receive_id_type=target.receive_id_type,
        message_id=str(message_id) if message_id else None,
        request_uuid=resolved_uuid,
        card=card,
        card_size_bytes=size.bytes,
        raw_response=response,
    )


def send_reminder_task_card(
    reminder: Reminder,
    *,
    settings: Settings | None = None,
    v1_client: CardSender | None = None,
    v2_client: CardSender | None = None,
) -> TaskCardDeliveryResult:
    """Send a scheduled reminder using its configured card delivery mode."""

    if reminder.task is None:
        raise ValueError("Reminder.task must be loaded before delivery")

    resolved_settings = settings or get_settings()
    receive_id, receive_id_type = reminder_target(reminder, resolved_settings)
    request_uuid = reminder.request_uuid or reminder_request_uuid(reminder)
    mode = reminder_delivery_mode(reminder)

    if mode == ReminderDeliveryMode.FEISHU_CARD_V1.value:
        card = build_task_card_v1(reminder.task, note=reminder.note)
        size = serialized_card_v1_size(card)
        sender = v1_client or FeishuCardV1Client.from_settings(resolved_settings)
        response = sender.send_card(
            receive_id=receive_id,
            receive_id_type=receive_id_type,
            card=card,
            uuid=request_uuid,
        )
        provider = "feishu_card_v1"
    else:
        card = build_task_card_v2(reminder.task, note=reminder.note)
        size = serialized_card_size(card)
        sender = v2_client or FeishuCardClient.from_settings(resolved_settings)
        response = sender.send_card(
            receive_id=receive_id,
            receive_id_type=receive_id_type,
            card=card,
            uuid=request_uuid,
        )
        provider = "feishu_card_v2"

    message_id = response.get("data", {}).get("message_id") if isinstance(response.get("data"), dict) else None
    return TaskCardDeliveryResult(
        provider=provider,
        status="sent",
        task_id=reminder.task_id,
        receive_id_type=receive_id_type,
        message_id=str(message_id) if message_id else None,
        request_uuid=request_uuid,
        card=card,
        card_size_bytes=size.bytes,
        raw_response=response,
    )
