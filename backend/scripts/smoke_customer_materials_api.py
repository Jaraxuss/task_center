#!/usr/bin/env python3
"""
Smoke test for Customer Materials API consolidation.
Uses FastAPI TestClient with an in-memory SQLite database (no external services needed).

Covers:
  1. Create material with new v2 fields (customer_id, review_batch_id, material_type, etc.)
  2. Query by customer_id, status, review_batch_id
  3. mark-uploaded
  4. Material facts: add and query
  5. Legacy project query compatibility
  6. Update with v2 fields
  7. Review batch endpoint returns unified CustomerMaterialRead

Usage:
  cd /tmp/task-center-api-ds/backend
  python3 scripts/smoke_customer_materials_api.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime, timezone

# Ensure backend can be imported
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

import db as db_module
from db import Base
from fastapi.testclient import TestClient
from main import app


# ─────────────────────────────────────────────────────
# Helper: override get_db to use an in-memory SQLite DB
# ─────────────────────────────────────────────────────
def setup_test_db():
    """Create a temp file SQLite database and override the FastAPI dependency.
    
    NOTE: We must use a file-based database (not :memory:) because SQLite
    :memory: databases are per-connection, and SQLAlchemy's sessionmaker
    creates new connections from the pool that won't see tables created
    on a different connection.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    test_db_path = os.path.join(tempfile.mkdtemp(), "test_task_center.db")
    test_engine = create_engine(f"sqlite:///{test_db_path}", connect_args={"check_same_thread": False})
    TestSessionLocal = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)

    # Monkey-patch db module for test
    db_module.engine = test_engine
    db_module.SessionLocal = TestSessionLocal

    def _get_test_db():
        db_test = TestSessionLocal()
        try:
            yield db_test
        finally:
            db_test.close()

    # Override the FastAPI dependency
    app.dependency_overrides[db_module.get_db] = _get_test_db

    # Create all tables
    Base.metadata.create_all(bind=test_engine)

    return test_engine


def teardown_test_db(engine):
    """Clean up test database overrides."""
    if app.dependency_overrides:
        app.dependency_overrides = {}
    # Dispose the engine pool so we can delete the temp file
    engine.dispose()


# ─────────────────────────────────────────────────────
# Test helpers
# ─────────────────────────────────────────────────────
def green(msg: str) -> str:
    return f"\033[92m{msg}\033[0m"


def red(msg: str) -> str:
    return f"\033[91m{msg}\033[0m"


def assert_eq(actual, expected, label: str):
    if actual != expected:
        print(red(f"  FAIL [{label}]: expected {expected!r}, got {actual!r}"))
        return False
    return True


def assert_status(resp, expected_code: int, label: str):
    if resp.status_code != expected_code:
        print(red(f"  FAIL [{label}]: expected HTTP {expected_code}, got {resp.status_code}"))
        try:
            print(red(f"  Response: {resp.json()}"))
        except Exception:
            print(red(f"  Response text: {resp.text}"))
        return False
    return True


def create_customer(client: TestClient, name: str, key: str = None, area: str = None) -> int:
    """Create a test customer and return its ID."""
    resp = client.post("/api/customers", json=dict(
        name=name,
        key=key or name.lower().replace(" ", "_"),
        area=area or name,
        status="active",
    ))
    assert resp.status_code == 201, f"Failed to create customer: {resp.text}"
    return resp.json()["id"]


def create_fact(client: TestClient, customer_id: int, title: str, raw_markdown: str) -> int:
    """Create a test fact and return its ID."""
    resp = client.post("/api/facts", json=dict(
        customer_id=customer_id,
        fact_date="2026-05-01T10:00:00Z",
        title=title,
        raw_markdown=raw_markdown,
        status="draft",
    ))
    assert resp.status_code == 201, f"Failed to create fact: {resp.text}"
    return resp.json()["id"]


def create_review_batch(client: TestClient, title: str) -> int:
    """Create a test review batch and return its ID."""
    resp = client.post("/api/review-batches", json=dict(
        title=title,
        batch_type="weekly_customer_summary",
        period_start="2026-04-27T00:00:00Z",
        period_end="2026-05-03T23:59:59Z",
        status="pending",
    ))
    assert resp.status_code == 201, f"Failed to create review batch: {resp.text}"
    return resp.json()["id"]


# ─────────────────────────────────────────────────────
# Test cases
# ─────────────────────────────────────────────────────

def test_create_material_with_v2_fields(client: TestClient, customer_id: int, review_batch_id: int):
    """Test 1: Create a material using the consolidated endpoint with new v2 fields."""
    print("\n--- Test 1: Create material with v2 fields ---")

    payload = {
        "customer_id": customer_id,
        "review_batch_id": review_batch_id,
        "title": "Weekly Summary - Acme Corp",
        "material_type": "period_summary",
        "period_start": "2026-04-27T00:00:00Z",
        "period_end": "2026-05-03T23:59:59Z",
        "raw_facts_markdown": "# Raw Facts\n- Something happened this week.",
        "summary_markdown": "# Summary\nThis week was productive.",
        "insights_markdown": "# Insights\nKey insight: growth trend.",
        "generation_meta": {"model": "test", "tokens": 1234},
        "status": "pending",
        # Legacy field (optional; auto-filled from customer.area)
        "source_refs": {"chat_id": "oc_test"},
    }

    resp = client.post("/api/customer-materials", json=payload)
    assert_status(resp, 201, "POST /api/customer-materials (v2 fields)")

    data = resp.json()
    assert_eq(data["title"], "Weekly Summary - Acme Corp", "title")
    assert_eq(data["customer_id"], customer_id, "customer_id")
    assert_eq(data["review_batch_id"], review_batch_id, "review_batch_id")
    assert_eq(data["material_type"], "period_summary", "material_type")
    assert_eq(data["status"], "pending", "status")
    assert_eq(data.get("raw_facts_markdown"), "# Raw Facts\n- Something happened this week.", "raw_facts_markdown")
    assert_eq(data.get("summary_markdown"), "# Summary\nThis week was productive.", "summary_markdown")
    assert_eq(data.get("insights_markdown"), "# Insights\nKey insight: growth trend.", "insights_markdown")
    assert_eq(data.get("generation_meta"), {"model": "test", "tokens": 1234}, "generation_meta")
    assert data.get("project") is not None, "Legacy project should be auto-filled"

    print(green("  PASS: Material created with all v2 fields"))
    return data["id"]


def test_create_material_legacy_path(client: TestClient):
    """Test 2: Create a material using legacy-only fields (backward compatibility)."""
    print("\n--- Test 2: Create material with legacy-only fields (backward compat) ---")

    payload = {
        "project": "LegacyClient",
        "title": "Legacy Material",
        "source_type": "text",
        "source": "chat",
        "candidate_markdown": "# Legacy Candidate Content",
        "status": "pending",
    }

    resp = client.post("/api/customer-materials", json=payload)
    assert_status(resp, 201, "POST /api/customer-materials (legacy)")

    data = resp.json()
    assert_eq(data["project"], "LegacyClient", "project")
    assert_eq(data["title"], "Legacy Material", "title")

    print(green("  PASS: Legacy material created successfully"))
    return data["id"]


def test_query_by_customer_id(client: TestClient, customer_id: int, expected_material_id: int):
    """Test 3: Query materials by customer_id."""
    print("\n--- Test 3: Query by customer_id ---")

    resp = client.get(f"/api/customer-materials?customer_id={customer_id}")
    assert_status(resp, 200, "GET by customer_id")

    data = resp.json()
    assert len(data) >= 1, f"Expected at least 1 material for customer_id={customer_id}, got {len(data)}"
    ids = [m["id"] for m in data]
    assert expected_material_id in ids, f"Expected to find material {expected_material_id}"
    assert all(m["customer_id"] == customer_id for m in data), "All returned materials must match customer_id"

    print(green(f"  PASS: Found {len(data)} materials for customer_id={customer_id}"))


def test_query_by_status(client: TestClient, status: str = "pending"):
    """Test 4: Query materials by status."""
    print(f"\n--- Test 4: Query by status={status} ---")

    resp = client.get(f"/api/customer-materials?status={status}")
    assert_status(resp, 200, f"GET by status={status}")

    data = resp.json()
    assert len(data) >= 1, f"Expected at least 1 material with status={status}"
    assert all(m["status"] == status for m in data), f"All returned materials must have status={status}"

    print(green(f"  PASS: Found {len(data)} materials with status={status}"))


def test_query_by_review_batch_id(client: TestClient, review_batch_id: int, expected_material_id: int):
    """Test 5: Query materials by review_batch_id."""
    print("\n--- Test 5: Query by review_batch_id ---")

    resp = client.get(f"/api/customer-materials?review_batch_id={review_batch_id}")
    assert_status(resp, 200, "GET by review_batch_id")

    data = resp.json()
    assert len(data) >= 1, f"Expected at least 1 material for review_batch_id={review_batch_id}"
    ids = [m["id"] for m in data]
    assert expected_material_id in ids, f"Expected material {expected_material_id} for review_batch_id={review_batch_id}"
    assert all(m["review_batch_id"] == review_batch_id for m in data)

    print(green(f"  PASS: Found {len(data)} materials for review_batch_id={review_batch_id}"))


def test_mark_uploaded(client: TestClient, material_id: int):
    """Test 6: Mark a material as uploaded."""
    print("\n--- Test 6: mark-uploaded ---")

    resp = client.post(f"/api/customer-materials/{material_id}/mark-uploaded")
    assert_status(resp, 200, "POST mark-uploaded")

    data = resp.json()
    assert_eq(data["status"], "uploaded", "status should be 'uploaded' after mark-uploaded")

    # Verify via GET
    resp2 = client.get(f"/api/customer-materials/{material_id}")
    assert_status(resp2, 200, "GET after mark-uploaded")
    assert_eq(resp2.json()["status"], "uploaded", "GET status should be 'uploaded'")

    print(green("  PASS: Material marked as uploaded"))


def test_material_facts_add_and_query(client: TestClient, material_id: int, fact_ids: list[int]):
    """Test 7: Add facts to a material and query them."""
    print("\n--- Test 7: Material facts add and query ---")

    # Add facts
    for idx, fact_id in enumerate(fact_ids):
        resp = client.post(f"/api/customer-materials/{material_id}/facts", json={
            "fact_id": fact_id,
            "sort_order": idx,
        })
        assert_status(resp, 201, f"POST material/{material_id}/facts (fact_id={fact_id})")
        assert_eq(resp.json()["fact_id"], fact_id, f"fact_id {fact_id}")
        assert_eq(resp.json()["material_id"], material_id, f"material_id {material_id}")

    # Query facts
    resp = client.get(f"/api/customer-materials/{material_id}/facts")
    assert_status(resp, 200, f"GET material/{material_id}/facts")

    data = resp.json()
    assert_eq(len(data), len(fact_ids), f"expected {len(fact_ids)} facts, got {len(data)}")
    returned_fact_ids = [mf["fact_id"] for mf in data]
    assert_eq(sorted(returned_fact_ids), sorted(fact_ids), "all fact_ids should be present")
    # Verify sort_order
    for i, mf in enumerate(data):
        assert_eq(mf["sort_order"], i, f"sort_order of fact #{i}")

    print(green(f"  PASS: {len(fact_ids)} facts added and queried successfully"))


def test_legacy_project_query(client: TestClient):
    """Test 8: Legacy project query still works."""
    print("\n--- Test 8: Legacy project query compatibility ---")

    # Query using the legacy 'project' filter
    resp = client.get("/api/customer-materials?project=LegacyClient")
    assert_status(resp, 200, "GET by legacy project")

    data = resp.json()
    assert len(data) >= 1, "Expected at least 1 material for project=LegacyClient"
    assert any(m["project"] == "LegacyClient" for m in data), "LegacyClient material should be present"

    # Also search via 'q' parameter
    resp2 = client.get("/api/customer-materials?q=Legacy")
    assert_status(resp2, 200, "GET by q=Legacy")
    assert len(resp2.json()) >= 1, "Search should find legacy material"

    print(green("  PASS: Legacy project query works correctly"))


def test_get_single_material_with_v2_fields(client: TestClient, material_id: int):
    """Test 9: GET single material returns unified schema with v2 fields."""
    print("\n--- Test 9: GET single material returns unified schema ---")

    resp = client.get(f"/api/customer-materials/{material_id}")
    assert_status(resp, 200, f"GET /api/customer-materials/{material_id}")

    data = resp.json()
    assert_eq(data["id"], material_id, "id")
    # Verify v2 fields are present in the response
    for field in ["customer_id", "review_batch_id", "material_type", "raw_facts_markdown", "summary_markdown",
                  "insights_markdown", "generation_meta"]:
        assert field in data, f"v2 field '{field}' must be present in response"

    print(green("  PASS: Single material returned with unified schema"))


def test_update_material_v2_fields(client: TestClient, material_id: int):
    """Test 10: Update material with v2 fields (summary, insights, generation_meta)."""
    print("\n--- Test 10: Update material with v2 fields ---")

    resp = client.patch(f"/api/customer-materials/{material_id}", json={
        "summary_markdown": "Updated summary with new insights.",
        "insights_markdown": "Updated: customer is expanding.",
        "generation_meta": {"model": "v2", "tokens": 2500, "version": 2},
        "raw_facts_markdown": "Updated raw facts content.",
    })
    assert_status(resp, 200, f"PATCH /api/customer-materials/{material_id}")

    data = resp.json()
    assert_eq(data.get("summary_markdown"), "Updated summary with new insights.", "summary_markdown")
    assert_eq(data.get("insights_markdown"), "Updated: customer is expanding.", "insights_markdown")
    assert_eq(data.get("raw_facts_markdown"), "Updated raw facts content.", "raw_facts_markdown")
    assert_eq(data.get("generation_meta"), {"model": "v2", "tokens": 2500, "version": 2}, "generation_meta")

    # Verify old compat field (project) still present
    assert "project" in data, "Legacy 'project' field should still be present"

    print(green("  PASS: Material updated with v2 fields"))


def test_update_with_clear_fields(client: TestClient, material_id: int):
    """Test 11: Update clearing project_v2_id and review_batch_id."""
    print("\n--- Test 11: Update clearing v2 associations ---")

    resp = client.patch(f"/api/customer-materials/{material_id}", json={
        "clear_project_v2": True,
        "clear_batch": True,
    })
    assert_status(resp, 200, "PATCH with clear_project_v2 / clear_batch")

    data = resp.json()
    # After clearing, these should be None
    assert_eq(data.get("project_v2_id"), None, "project_v2_id cleared")
    assert_eq(data.get("review_batch_id"), None, "review_batch_id cleared")

    print(green("  PASS: v2 associations cleared successfully"))


def test_review_batch_customer_materials(client: TestClient, review_batch_id: int, material_id: int):
    """Test 12: Review batch endpoint returns unified CustomerMaterialRead."""
    print("\n--- Test 12: Review batch materials endpoint returns unified schema ---")

    # First, associate a material with the batch (create one via main endpoint)
    resp_create = client.post("/api/customer-materials", json={
        "customer_id": 1,
        "review_batch_id": review_batch_id,
        "title": "Batch Material Test",
        "material_type": "period_summary",
    })
    assert resp_create.status_code == 201, f"Failed to create batch material: {resp_create.text}"

    resp = client.get(f"/api/review-batches/{review_batch_id}/customer-materials")
    assert_status(resp, 200, f"GET /api/review-batches/{review_batch_id}/customer-materials")

    data = resp.json()
    assert len(data) >= 1, "Expected materials under review batch"
    # Verify it returns the unified schema (CustomerMaterialRead) not CustomerMaterialV2Read
    for m in data:
        assert "project" in m, "unified schema must have 'project' (legacy field)"
        assert "customer_id" in m, "unified schema must have 'customer_id' (v2 field)"
        assert m["review_batch_id"] == review_batch_id, "review_batch_id must match"

    print(green("  PASS: Review batch materials use unified CustomerMaterialRead"))


def test_material_type_filter(client: TestClient):
    """Test 13: Filter by material_type query param."""
    print("\n--- Test 13: Filter by material_type ---")

    # Create materials of different types
    client.post("/api/customer-materials", json={
        "customer_id": 1,
        "title": "Meeting Note Test",
        "material_type": "meeting_note",
        "project": "Test",
    })
    client.post("/api/customer-materials", json={
        "customer_id": 1,
        "title": "Fact Bundle Test",
        "material_type": "fact_bundle",
        "project": "Test",
    })

    resp = client.get("/api/customer-materials?material_type=meeting_note")
    assert_status(resp, 200, "GET material_type=meeting_note")

    data = resp.json()
    assert all(m["material_type"] == "meeting_note" for m in data), "All must be meeting_note"

    resp2 = client.get("/api/customer-materials?material_type=fact_bundle")
    assert_status(resp2, 200, "GET material_type=fact_bundle")
    assert all(m["material_type"] == "fact_bundle" for m in resp2.json()), "All must be fact_bundle"

    print(green("  PASS: material_type filter works"))


def test_404_on_missing(client: TestClient):
    """Test 14: 404 on missing material and mark-uploaded/facts on missing."""
    print("\n--- Test 14: 404 on missing resources ---")

    # Non-existent material
    resp = client.get("/api/customer-materials/99999")
    assert_status(resp, 404, "GET non-existent material")

    # Mark uploaded on non-existent
    resp2 = client.post("/api/customer-materials/99999/mark-uploaded")
    assert_status(resp2, 404, "POST mark-uploaded on non-existent")

    # Facts on non-existent
    resp3 = client.get("/api/customer-materials/99999/facts")
    assert_status(resp3, 404, "GET facts on non-existent")

    print(green("  PASS: 404 responses correct"))


# ─────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("Customer Materials API Consolidation Smoke Tests")
    print("=" * 70)

    engine = setup_test_db()
    client = TestClient(app, base_url="http://testserver")

    try:
        # Setup
        print("\n--- Setup: Creating test fixtures ---")
        customer_id = create_customer(client, "Acme Corp", "acme", "Acme Corp")
        fact_id_1 = create_fact(client, customer_id, "Fact Alpha", "Some fact about Acme.")
        fact_id_2 = create_fact(client, customer_id, "Fact Beta", "Another fact about Acme.")
        review_batch_id = create_review_batch(client, "Weekly Review Batch W18")
        print(f"  Customer ID: {customer_id}")
        print(f"  Fact IDs: {fact_id_1}, {fact_id_2}")
        print(f"  Review Batch ID: {review_batch_id}")

        # Test 1-2: Create
        material_id = test_create_material_with_v2_fields(client, customer_id, review_batch_id)
        legacy_material_id = test_create_material_legacy_path(client)

        # Test 3-5: Query
        test_query_by_customer_id(client, customer_id, material_id)
        test_query_by_status(client, "pending")
        test_query_by_review_batch_id(client, review_batch_id, material_id)

        # Test 6: mark-uploaded
        test_mark_uploaded(client, legacy_material_id)

        # Test 7: facts
        test_material_facts_add_and_query(client, material_id, [fact_id_1, fact_id_2])

        # Test 8: legacy project query
        test_legacy_project_query(client)

        # Test 9: GET single
        test_get_single_material_with_v2_fields(client, material_id)

        # Test 10: UPDATE
        test_update_material_v2_fields(client, material_id)

        # Test 11: Clear fields
        test_update_with_clear_fields(client, material_id)

        # Test 12: Review batch endpoint
        test_review_batch_customer_materials(client, review_batch_id, material_id)

        # Test 13: Material type filter
        test_material_type_filter(client)

        # Test 14: 404
        test_404_on_missing(client)

        # All tests use assert functions internally and will raise on failure.
        # If we reach here without exceptions, all passed.
        print("\n" + "=" * 70)
        print("RESULTS SUMMARY")
        print("=" * 70)
        print(green("\n✓ All 14 smoke test scenarios passed!\n"))

    finally:
        teardown_test_db(engine)

    return 0


if __name__ == "__main__":
    sys.exit(main())