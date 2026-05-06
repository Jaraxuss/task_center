"""Pytest bootstrap with strict production-DB isolation.

Safety contract
---------------
Tests MUST NEVER touch the production SQLite database. Two independent
layers enforce this:

1. Before any backend module is imported, ``TASK_CENTER_DATABASE_PATH`` is
   set to a temp file under the OS temp dir. ``config.get_settings`` and
   ``db`` (which reads settings at import time) will resolve to that path.

2. A session-scoped guard fixture asserts the resolved DB path lives
   outside ``backend/data`` and contains the substring ``task_center_test``.
   If either assertion fails the entire test run aborts before any DB work
   happens.

Tests interact with the database only through the fixtures here
(``db_session``, ``api_client``). Direct imports of ``db.engine`` are fine
because by the time they execute the engine is already bound to the temp DB.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest

# --- Step 1: prepare an isolated temp DB BEFORE any backend imports. -------

_TEST_DB_DIR = Path(tempfile.mkdtemp(prefix="task_center_test_"))
_TEST_DB_PATH = _TEST_DB_DIR / "task_center_test.db"

# Wipe any inherited env that could redirect the DB elsewhere.
os.environ.pop("TASK_CENTER_DATABASE_URL", None)
os.environ["TASK_CENTER_DATABASE_PATH"] = str(_TEST_DB_PATH)

# Make the backend package importable without installing it. ``conftest.py``
# lives in ``backend/tests``; ``backend`` itself is a flat module directory.
_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

# Import after env + sys.path are configured.
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from db import DATABASE_PATH, Base, SessionLocal, engine, get_db  # noqa: E402

# --- Step 2: belt-and-suspenders guard. ------------------------------------

_PRODUCTION_DATA_DIR = (_BACKEND_DIR / "data").resolve()


def _assert_isolated_db() -> None:
    resolved = Path(str(DATABASE_PATH)).resolve()
    engine_url = str(engine.url)
    if "task_center_test" not in resolved.name:
        raise RuntimeError(
            f"Refusing to run tests: resolved DB path {resolved} does not "
            f"contain 'task_center_test'."
        )
    try:
        resolved.relative_to(_PRODUCTION_DATA_DIR)
    except ValueError:
        # Good: the resolved path is NOT inside backend/data.
        pass
    else:
        raise RuntimeError(
            f"Refusing to run tests: resolved DB path {resolved} is inside "
            f"the production data dir {_PRODUCTION_DATA_DIR}."
        )
    if str(_PRODUCTION_DATA_DIR) in engine_url:
        raise RuntimeError(
            f"Refusing to run tests: engine.url {engine_url} references the "
            f"production data dir {_PRODUCTION_DATA_DIR}."
        )


# Run the guard at module import time so a misconfigured run aborts before
# any fixture code or test module is collected.
_assert_isolated_db()


# --- Fixtures --------------------------------------------------------------


@pytest.fixture(scope="session", autouse=True)
def _initialize_schema() -> Generator[None, None, None]:
    """Create all tables on the temp DB once per session, then clean up."""

    Base.metadata.create_all(bind=engine)
    try:
        yield
    finally:
        engine.dispose()
        # Best-effort cleanup of the temp dir; never fail teardown over it.
        shutil.rmtree(_TEST_DB_DIR, ignore_errors=True)


@pytest.fixture(autouse=True)
def _truncate_tables() -> Generator[None, None, None]:
    """Wipe every table between tests to keep them order-independent."""

    yield
    # DELETE rather than DROP/CREATE: keeps schema, fast for SQLite.
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.exec_driver_sql(f"DELETE FROM {table.name}")


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    """A short-lived SQLAlchemy session bound to the temp DB."""

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def api_client() -> Generator[TestClient, None, None]:
    """A FastAPI TestClient with ``get_db`` overridden to the temp DB.

    Importing ``main`` here (lazily) keeps fixture-less tests free of
    FastAPI startup cost.
    """

    from main import app  # noqa: WPS433  (intentional lazy import)

    def _override_get_db() -> Generator[Session, None, None]:
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _override_get_db
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_db, None)
