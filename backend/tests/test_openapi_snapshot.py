"""Verify that the checked-in openapi.json matches the live FastAPI spec.

If this test fails, run `make openapi` from the project root to regenerate
the snapshot, then commit both the backend change and the updated spec.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

SPEC_PATH = Path(__file__).resolve().parents[2] / "mobile_frontend" / "openapi.json"


@pytest.fixture()
def live_spec():
    from main import app

    return app.openapi()


def test_openapi_snapshot_matches(live_spec: dict):
    if not SPEC_PATH.exists():
        pytest.fail(
            f"openapi.json not found at {SPEC_PATH}. "
            "Run `make openapi` from the project root first."
        )

    checked_in = json.loads(SPEC_PATH.read_text(encoding="utf-8"))

    # Sort keys for deterministic comparison
    live_str = json.dumps(live_spec, sort_keys=True, ensure_ascii=False)
    checked_str = json.dumps(checked_in, sort_keys=True, ensure_ascii=False)

    assert live_str == checked_str, (
        "openapi.json is out of date. Run `make openapi` from the project root "
        "and commit the updated spec."
    )
