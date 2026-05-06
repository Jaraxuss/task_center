"""Sanity tests: prove the test runner is bound to a temp DB.

If these ever fail, do NOT weaken them; fix the test bootstrap instead.
"""

from __future__ import annotations

from pathlib import Path

from db import DATABASE_PATH, engine

PRODUCTION_DATA_DIR = (Path(__file__).resolve().parent.parent / "data").resolve()


def test_resolved_path_is_temp_test_db() -> None:
    resolved = Path(str(DATABASE_PATH)).resolve()
    assert "task_center_test" in resolved.name, (
        f"Expected resolved DB path to contain 'task_center_test', got {resolved}"
    )


def test_resolved_path_is_outside_production_data_dir() -> None:
    resolved = Path(str(DATABASE_PATH)).resolve()
    try:
        resolved.relative_to(PRODUCTION_DATA_DIR)
    except ValueError:
        return
    raise AssertionError(
        f"Test DB path {resolved} unexpectedly inside production dir "
        f"{PRODUCTION_DATA_DIR}"
    )


def test_engine_url_does_not_reference_production_dir() -> None:
    assert str(PRODUCTION_DATA_DIR) not in str(engine.url), (
        f"engine.url {engine.url} unexpectedly references production data dir"
    )
