"""Tests for scripts/backfill_task_project_id.py — 3 branches:
1. match: task.project matches an existing Project → link
2. no-match-create: no Project exists → create + link
3. customer-less: task has project string but no customer_id

NOTE: These tests are SKIPPED because Task.project has been removed from
the ORM (4.A.5).  The backfill script now uses raw SQL and must be run
against a real database that still has the column.
"""

from __future__ import annotations

import pytest

from sqlalchemy.orm import Session

from models import Customer, Project, ProjectStatus, ProjectType, Task, TaskStatus

pytestmark = pytest.mark.skip(reason="Task.project column removed from ORM — backfill tests are pre-migration only")


def _make_customer(db: Session, name: str, area: str = "customer") -> Customer:
    c = Customer(name=name, area=area)
    db.add(c)
    db.flush()
    return c


def _make_project(db: Session, name: str, customer_id: int | None = None, area: str | None = None) -> Project:
    p = Project(
        name=name,
        customer_id=customer_id,
        project_type=ProjectType.CUSTOMER.value,
        status=ProjectStatus.ACTIVE.value,
        area=area,
    )
    db.add(p)
    db.flush()
    return p


def _make_task(db: Session, title: str, project: str | None, customer_id: int | None = None, project_id: int | None = None) -> Task:
    t = Task(
        title=title,
        project=project,
        customer_id=customer_id,
        project_id=project_id,
        status=TaskStatus.TODO.value,
    )
    db.add(t)
    db.flush()
    return t


class TestBackfillMatch:
    """Branch 1: task.project matches an existing Project row → link without creating."""

    def test_links_existing_project(self, db_session: Session) -> None:
        from scripts.backfill_task_project_id import backfill

        customer = _make_customer(db_session, "Acme")
        project = _make_project(db_session, "客户_Acme", customer_id=customer.id, area="customer")
        task = _make_task(db_session, "Follow up", project="客户_Acme", customer_id=customer.id)
        db_session.commit()

        report = backfill(db_session, apply=True)

        db_session.refresh(task)
        assert task.project_id == project.id
        assert report["matched"] == 1
        assert report["created"] == 0


class TestBackfillCreate:
    """Branch 2: no matching Project exists → create a new one + link."""

    def test_creates_and_links_project(self, db_session: Session) -> None:
        from scripts.backfill_task_project_id import backfill

        customer = _make_customer(db_session, "NewCo", area="customer")
        task = _make_task(db_session, "Onboarding", project="客户_NewCo", customer_id=customer.id)
        db_session.commit()

        report = backfill(db_session, apply=True)

        db_session.refresh(task)
        assert task.project_id is not None
        assert report["created"] == 1
        assert report["matched"] == 0

        # Verify the newly created project
        new_project = db_session.get(Project, task.project_id)
        assert new_project is not None
        assert new_project.name == "客户_NewCo"
        assert new_project.customer_id == customer.id
        assert new_project.area == "customer"


class TestBackfillCustomerless:
    """Branch 3: task has project string but customer_id is NULL."""

    def test_creates_project_without_customer(self, db_session: Session) -> None:
        from scripts.backfill_task_project_id import backfill

        task = _make_task(db_session, "Internal task", project="内部协同", customer_id=None)
        db_session.commit()

        report = backfill(db_session, apply=True)

        db_session.refresh(task)
        assert task.project_id is not None
        assert report["created"] == 1

        new_project = db_session.get(Project, task.project_id)
        assert new_project is not None
        assert new_project.name == "内部协同"
        assert new_project.customer_id is None


class TestBackfillSkips:
    """Edge cases: already-filled project_id, empty project string."""

    def test_skips_already_linked(self, db_session: Session) -> None:
        from scripts.backfill_task_project_id import backfill

        customer = _make_customer(db_session, "Existing")
        project = _make_project(db_session, "客户_Existing", customer_id=customer.id)
        task = _make_task(db_session, "Already linked", project="客户_Existing",
                          customer_id=customer.id, project_id=project.id)
        db_session.commit()

        report = backfill(db_session, apply=True)

        assert report["total_candidates"] == 0
        assert report["matched"] == 0
        assert report["created"] == 0

    def test_dry_run_no_changes(self, db_session: Session) -> None:
        from scripts.backfill_task_project_id import backfill

        customer = _make_customer(db_session, "DryRunCo")
        task = _make_task(db_session, "Dry run test", project="客户_DryRunCo", customer_id=customer.id)
        db_session.commit()

        report = backfill(db_session, apply=False)

        db_session.refresh(task)
        assert task.project_id is None  # no change
        assert report["total_candidates"] == 1
        assert report["created"] == 1  # reported but not persisted
