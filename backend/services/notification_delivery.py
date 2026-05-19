"""Notification delivery services for TaskCenter."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from config import Settings, get_settings
from models import Task
from services.feishu_card import FeishuCardClient, FeishuTarget, serialized_card_size
from services.task_card_builder import build_task_card_v2


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

    updated_at = task.updated_at.isoformat() if task.updated_at else "unknown"
    return f"task:{task.id}:manual-card:{updated_at}"


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
