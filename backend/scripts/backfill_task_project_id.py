"""Backfill tasks.project_id from tasks.project string.

MUST be run BEFORE the alembic migration that drops tasks.project.

For every task where `project IS NOT NULL AND project_id IS NULL`:
  1. Look for a matching Project row by (customer_id, name=project).
  2. If found → set task.project_id to that project's id.
  3. If not found → create a new Project row (using task.project as name,
     task.customer_id as FK, customer.area if available), then link.

Usage:
  python3 backend/scripts/backfill_task_project_id.py --dry-run
  python3 backend/scripts/backfill_task_project_id.py --apply
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from db import SessionLocal
from models import Customer, Project, ProjectStatus, ProjectType, Task


def find_project(db: Session, customer_id: int | None, project_name: str) -> Project | None:
    """Find an existing Project by customer_id + name (exact match)."""
    stmt = select(Project).where(Project.name == project_name)
    if customer_id is not None:
        stmt = stmt.where(Project.customer_id == customer_id)
    else:
        stmt = stmt.where(Project.customer_id.is_(None))
    return db.scalars(stmt).first()


def resolve_area(db: Session, customer_id: int | None) -> str | None:
    """Look up customer.area for the given customer_id."""
    if customer_id is None:
        return None
    customer = db.get(Customer, customer_id)
    return customer.area if customer else None


def resolve_project_type(area: str | None) -> str:
    """Derive project_type from area string."""
    if area == "personal":
        return ProjectType.PERSONAL.value
    if area == "internal":
        return ProjectType.INTERNAL.value
    return ProjectType.CUSTOMER.value


def backfill(db: Session, *, apply: bool = False) -> dict:
    """Run the backfill. Returns a report dict."""
    # Use raw SQL to read the legacy 'project' column since it has been
    # removed from the ORM (but still exists in the DB until migration runs).
    rows = db.execute(
        text("SELECT id, project, customer_id, area FROM tasks "
             "WHERE project IS NOT NULL AND project_id IS NULL")
    ).fetchall()

    matched = 0
    created = 0
    skipped_empty = 0
    details: list[dict] = []

    for row in rows:
        task_id, raw_project, customer_id, task_area = row
        project_name = (raw_project or "").strip()
        if not project_name:
            skipped_empty += 1
            continue
        task = db.get(Task, task_id)
        if task is None:
            skipped_empty += 1
            continue

        project = find_project(db, customer_id, project_name)
        action: str

        if project is None:
            # Also try matching without customer constraint (for tasks with
            # customer_id=NULL whose project name matches an existing Project).
            if customer_id is not None:
                project = find_project(db, None, project_name)

        if project is not None:
            action = "matched"
            matched += 1
        else:
            area = resolve_area(db, customer_id) or task_area
            project = Project(
                customer_id=customer_id,
                name=project_name,
                project_type=resolve_project_type(area),
                status=ProjectStatus.ACTIVE.value,
                area=area,
            )
            if apply:
                db.add(project)
                db.flush()  # need project.id
            action = "created"
            created += 1

        details.append({
            "task_id": task_id,
            "task_title": task.title if task else "(unknown)",
            "project_name": project_name,
            "customer_id": customer_id,
            "project_id": project.id if apply else "(pending)",
            "action": action,
        })

        if apply:
            task.project_id = project.id

    if apply:
        db.commit()

    return {
        "total_candidates": len(tasks),
        "matched": matched,
        "created": created,
        "skipped_empty": skipped_empty,
        "details": details,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill task.project_id from task.project string")
    parser.add_argument("--apply", action="store_true", help="Actually write changes; without this flag it's dry-run")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        report = backfill(db, apply=args.apply)

        print(f"\n=== {'APPLIED' if args.apply else 'DRY-RUN'} ===")
        print(f"  total candidates : {report['total_candidates']}")
        print(f"  matched existing : {report['matched']}")
        print(f"  created new      : {report['created']}")
        print(f"  skipped (empty)  : {report['skipped_empty']}")

        if report["details"]:
            print(f"\n=== sample (first 30) ===")
            for row in report["details"][:30]:
                print(f"  task#{row['task_id']} [{row['action']}] project={row['project_name']!r} "
                      f"customer_id={row['customer_id']} → project_id={row['project_id']}  | {row['task_title']}")

        if not args.apply:
            print("\n[dry-run] No changes written. Pass --apply to execute.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
