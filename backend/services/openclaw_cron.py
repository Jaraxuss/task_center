"""OpenClaw cron CLI adapter for AI-backed reminders."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from typing import Protocol

from models import Reminder, Task
from timeutils import APP_TIMEZONE


class CommandRunner(Protocol):
    def __call__(self, args: list[str]) -> subprocess.CompletedProcess[str]: ...


class OpenClawCronError(RuntimeError):
    """Raised when an OpenClaw cron CLI operation fails."""


@dataclass(frozen=True)
class OpenClawCronResult:
    job_id: str | None
    stdout: str
    stderr: str


def run_openclaw(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, text=True, capture_output=True, check=False)


def parse_cron_job_id(stdout: str) -> str | None:
    """Best-effort job id parser.

    TODO: Replace this after validating the stable `openclaw cron add` output
    shape, preferably with a JSON flag if the CLI supports one.
    """

    patterns = (
        r"job(?:\s+id)?[:=]\s*([A-Za-z0-9_.:-]+)",
        r"id[:=]\s*([A-Za-z0-9_.:-]+)",
        r"created\s+([A-Za-z0-9_.:-]+)",
    )
    for pattern in patterns:
        match = re.search(pattern, stdout, flags=re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def _target_arg(reminder: Reminder) -> str:
    receive_id = reminder.receive_id
    if not receive_id:
        raise OpenClawCronError("AI reminder requires receive_id for OpenClaw delivery")
    if receive_id.startswith(("user:", "chat:")):
        return receive_id
    receive_id_type = reminder.receive_id_type or "open_id"
    if receive_id_type == "chat_id":
        return f"chat:{receive_id}"
    return f"user:{receive_id}"


def create_ai_reminder_job(
    reminder: Reminder,
    task: Task,
    *,
    runner: CommandRunner = run_openclaw,
) -> OpenClawCronResult:
    if not reminder.ai_prompt:
        raise OpenClawCronError("AI reminder requires ai_prompt")

    remind_at = reminder.remind_at.astimezone(APP_TIMEZONE).isoformat()
    args = [
        "openclaw",
        "cron",
        "add",
        "--name",
        f"TaskCenter AI reminder #{reminder.id} task #{task.id}",
        "--at",
        remind_at,
        "--session",
        "isolated",
        "--message",
        reminder.ai_prompt,
        "--announce",
        "--channel",
        "feishu",
        "--to",
        _target_arg(reminder),
        "--delete-after-run",
    ]
    result = runner(args)
    if result.returncode != 0:
        raise OpenClawCronError(
            f"openclaw cron add failed: returncode={result.returncode}, stdout={result.stdout}, stderr={result.stderr}"
        )
    return OpenClawCronResult(job_id=parse_cron_job_id(result.stdout), stdout=result.stdout, stderr=result.stderr)


def remove_ai_reminder_job(job_id: str, *, runner: CommandRunner = run_openclaw) -> OpenClawCronResult:
    result = runner(["openclaw", "cron", "rm", job_id])
    if result.returncode != 0:
        raise OpenClawCronError(
            f"openclaw cron rm failed: returncode={result.returncode}, stdout={result.stdout}, stderr={result.stderr}"
        )
    return OpenClawCronResult(job_id=job_id, stdout=result.stdout, stderr=result.stderr)
