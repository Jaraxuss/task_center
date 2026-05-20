"""Reminder worker service for TaskCenter-owned Feishu card delivery."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from config import Settings, get_settings
from models import Reminder, ReminderDeliveryMode, ReminderStatus, TaskStatus
from services.notification_delivery import CardSender, send_reminder_task_card
from timeutils import now_utc


class ReminderSender(Protocol):
    def __call__(
        self,
        reminder: Reminder,
        *,
        settings: Settings | None = None,
        v1_client: CardSender | None = None,
        v2_client: CardSender | None = None,
    ) -> object: ...


@dataclass(frozen=True)
class ReminderWorkerResult:
    processed: int = 0
    fired: int = 0
    canceled: int = 0
    failed: int = 0
    retried: int = 0


def due_card_reminders(db: Session) -> list[Reminder]:
    stmt = (
        select(Reminder)
        .options(selectinload(Reminder.task))
        .where(
            Reminder.status == ReminderStatus.SCHEDULED.value,
            Reminder.remind_at <= now_utc(),
            or_(
                Reminder.delivery_mode.is_(None),
                Reminder.delivery_mode.in_([
                    ReminderDeliveryMode.FEISHU_CARD_V2.value,
                    ReminderDeliveryMode.FEISHU_CARD_V1.value,
                ]),
            ),
        )
        .order_by(Reminder.remind_at.asc(), Reminder.id.asc())
    )
    return list(db.scalars(stmt).all())


def process_due_card_reminders(
    db: Session,
    *,
    settings: Settings | None = None,
    sender: ReminderSender = send_reminder_task_card,
    v1_client: CardSender | None = None,
    v2_client: CardSender | None = None,
) -> ReminderWorkerResult:
    """Process due TaskCenter-owned reminders once.

    OpenClaw-backed AI reminders are intentionally excluded; OpenClaw owns
    their clock once the cron job is created.
    """

    resolved_settings = settings or get_settings()
    processed = fired = canceled = failed = retried = 0

    for reminder in due_card_reminders(db):
        processed += 1
        if reminder.task.status in {TaskStatus.DONE.value, TaskStatus.CANCELED.value}:
            reminder.status = ReminderStatus.CANCELED.value
            canceled += 1
            continue

        reminder.request_uuid = reminder.request_uuid or f"tc-reminder-{reminder.id}"
        try:
            result = sender(
                reminder,
                settings=resolved_settings,
                v1_client=v1_client,
                v2_client=v2_client,
            )
        except Exception as exc:  # noqa: BLE001 - worker must record delivery failures, not crash the tick
            reminder.retry_count += 1
            reminder.last_error = str(exc)
            if reminder.retry_count >= resolved_settings.reminder_max_retries:
                reminder.status = ReminderStatus.FAILED.value
                failed += 1
            else:
                retried += 1
            continue

        reminder.status = ReminderStatus.FIRED.value
        reminder.fired_at = now_utc()
        reminder.message_id = result.message_id
        reminder.request_uuid = result.request_uuid
        reminder.last_error = None
        fired += 1

    db.commit()
    return ReminderWorkerResult(processed=processed, fired=fired, canceled=canceled, failed=failed, retried=retried)
