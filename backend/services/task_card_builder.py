"""Build TaskCenter task cards for Feishu delivery."""

from __future__ import annotations

from datetime import datetime

from models import Task
from services.feishu_card import text_to_card_v2
from services.feishu_card_v1 import text_to_card_v1
from timeutils import APP_TIMEZONE


def _format_local_datetime(value: datetime | None) -> str:
    if value is None:
        return "未设置"
    return value.astimezone(APP_TIMEZONE).strftime("%Y-%m-%d %H:%M")


def _trim_text(value: str | None, *, limit: int = 600) -> str | None:
    text = (value or "").strip()
    if not text:
        return None
    if len(text) <= limit:
        return text
    return f"{text[: limit - 1]}..."


def task_card_markdown(task: Task, *, note: str | None = None) -> str:
    """Return deterministic Markdown for a TaskCenter task reminder card."""

    lines = [
        f"**task_center #{task.id}**",
        "",
        f"**任务**：{task.title}",
        f"**状态**：{task.status}",
        f"**计划时间**：{_format_local_datetime(task.due_at)}（北京时间）",
    ]
    if task.deferred_to:
        lines.append(f"**延期到**：{_format_local_datetime(task.deferred_to)}（北京时间）")
    if task.project_rel:
        lines.append(f"**项目**：{task.project_rel.name}")
    if task.area:
        lines.append(f"**区域**：{task.area}")

    description = _trim_text(task.description)
    if description:
        lines.extend(["", "**任务备注**：", description])

    extra_note = _trim_text(note, limit=300)
    if extra_note:
        lines.extend(["", "**发送备注**：", extra_note])

    lines.extend(["", "由 TaskCenter 后端生成并发送。"])
    return "\n".join(lines)


def build_task_card_v2(task: Task, *, note: str | None = None) -> dict:
    """Build the default Feishu Card JSON 2.0 payload for a task."""

    markdown = task_card_markdown(task, note=note)
    return text_to_card_v2(
        markdown,
        title="TaskCenter 提醒",
        subtitle=f"task_center #{task.id}",
        template="blue",
        summary=f"task_center #{task.id}: {task.title}",
    )


def build_task_card_v1(task: Task, *, note: str | None = None) -> dict:
    """Build the fallback Feishu Card JSON 1.0 payload for a task."""

    markdown = task_card_markdown(task, note=note)
    return text_to_card_v1(
        markdown,
        title="TaskCenter 提醒",
        subtitle=f"task_center #{task.id}",
        template="blue",
    )
