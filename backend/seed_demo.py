from __future__ import annotations

from datetime import datetime, timedelta

from db import SessionLocal
from main import add_event, init_db
from models import EventType, Reminder, ReminderStatus, Task, TaskStatus


def run() -> None:
    init_db()
    db = SessionLocal()
    try:
        if db.query(Task).count() > 0:
            print("Database already has tasks, skip seeding.")
            return

        now = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
        samples = [
            Task(
                title="整理今日客户回访",
                description="把上午新增线索同步进 CRM，并补 2 个回访电话记录",
                due_at=now + timedelta(hours=2),
                status=TaskStatus.TODO.value,
                project="销售",
                tags_json='["客户", "跟进"]',
                source="seed",
            ),
            Task(
                title="确认联调接口字段",
                description="和前端对齐 dashboard today/board/history 三个接口返回",
                due_at=now + timedelta(hours=4),
                status=TaskStatus.DOING.value,
                project="task_center",
                tags_json='["联调", "API"]',
                source="seed",
            ),
            Task(
                title="补发本周周报",
                description="已经延到明早 09:30",
                due_at=now - timedelta(hours=3),
                deferred_to=now + timedelta(days=1, hours=1),
                status=TaskStatus.DEFERRED.value,
                project="运营",
                tags_json='["周报"]',
                source="seed",
            ),
        ]
        db.add_all(samples)
        db.flush()

        reminders = [
            Reminder(task_id=samples[0].id, remind_at=now + timedelta(hours=1), channel="local", status=ReminderStatus.SCHEDULED.value, note="出门前再看一眼"),
            Reminder(task_id=samples[1].id, remind_at=now + timedelta(hours=3), channel="local", status=ReminderStatus.SCHEDULED.value, note="联调会前提醒"),
        ]
        db.add_all(reminders)

        for task in samples:
            add_event(db, task, EventType.CREATED.value, {"source": "seed_demo"})
        add_event(db, samples[2], EventType.DEFERRED.value, {"reason": "等待上游数据", "deferred_to": samples[2].deferred_to.isoformat()})

        db.commit()
        print(f"Seeded {len(samples)} tasks and {len(reminders)} reminders.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
