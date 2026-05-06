"""Guard test: the Alembic baseline migration must stay in sync with the ORM.

If this fails, either:
- the ORM models changed and a new Alembic revision is needed, or
- the baseline migration drifted from ``Base.metadata`` somehow.

Run on the isolated test DB only; never touches production.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect

import models  # noqa: F401  -- registers tables on Base.metadata
from db import Base


BACKEND_DIR = Path(__file__).resolve().parent.parent


def _alembic_upgrade(target_db: Path) -> None:
    """Run ``alembic upgrade head`` against ``target_db`` in a subprocess.

    A subprocess is used because Alembic's ``env.py`` reads
    ``TASK_CENTER_DATABASE_PATH`` at module load; reusing the current process
    would still point at the test DB managed by ``conftest.py``.
    """

    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=str(BACKEND_DIR),
        env={
            "PATH": "/usr/bin:/bin",
            "TASK_CENTER_DATABASE_PATH": str(target_db),
        },
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(
            f"alembic upgrade failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )


def _table_columns(db_path: Path, exclude_alembic: bool = True) -> dict[str, list[tuple]]:
    engine = create_engine(f"sqlite:///{db_path}")
    inspector = inspect(engine)
    out: dict[str, list[tuple]] = {}
    for name in inspector.get_table_names():
        if exclude_alembic and name == "alembic_version":
            continue
        cols = []
        for col in inspector.get_columns(name):
            cols.append((col["name"], str(col["type"]), col["nullable"]))
        out[name] = sorted(cols)
    engine.dispose()
    return out


def test_alembic_head_matches_orm_metadata() -> None:
    pytest.importorskip("alembic")
    with tempfile.TemporaryDirectory(prefix="alembic_baseline_") as tmpdir:
        tmp = Path(tmpdir)
        alembic_db = tmp / "alembic.db"
        ref_db = tmp / "ref.db"

        _alembic_upgrade(alembic_db)

        ref_engine = create_engine(f"sqlite:///{ref_db}")
        Base.metadata.create_all(ref_engine)
        ref_engine.dispose()

        assert _table_columns(alembic_db) == _table_columns(ref_db), (
            "Alembic baseline migration drifted from ORM metadata. "
            "Generate a new revision with `alembic revision --autogenerate`."
        )
