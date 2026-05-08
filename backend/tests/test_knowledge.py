"""Tests for knowledge facts overview and knowledge preferences APIs."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _create_fact(api_client: TestClient, **overrides) -> dict:
    base = {
        "title": "测试事实",
        "raw_markdown": "测试 markdown 正文",
        "fact_date": "2026-05-06T10:00:00Z",
        "source_type": "manual_input",
        "value_types": ["客户需求"],
        "status": "confirmed",
    }
    base.update(overrides)
    response = api_client.post("/api/facts", json=base)
    assert response.status_code == 201, response.text
    return response.json()


def test_overview_empty(api_client: TestClient) -> None:
    response = api_client.get("/api/knowledge/facts/overview")
    assert response.status_code == 200
    data = response.json()
    assert data["total_fact_count"] == 0
    assert data["customers"] == []


def test_overview_aggregates_by_customer_and_project(api_client: TestClient) -> None:
    _create_fact(api_client, customer_id=1, project_id=10, title="fact a")
    _create_fact(api_client, customer_id=1, project_id=10, title="fact b")
    _create_fact(api_client, customer_id=1, project_id=11, title="fact c")
    _create_fact(api_client, customer_id=2, project_id=20, title="fact d")

    response = api_client.get("/api/knowledge/facts/overview")
    assert response.status_code == 200
    data = response.json()
    assert data["total_fact_count"] == 4

    customer_ids = {c["customer_id"] for c in data["customers"]}
    assert 1 in customer_ids
    assert 2 in customer_ids

    c1 = next(c for c in data["customers"] if c["customer_id"] == 1)
    assert c1["fact_count"] == 3
    assert c1["project_count"] == 2

    pids_c1 = {p["project_id"] for p in c1["projects"]}
    assert 10 in pids_c1
    assert 11 in pids_c1

    c2 = next(c for c in data["customers"] if c["customer_id"] == 2)
    assert c2["fact_count"] == 1
    assert c2["project_count"] == 1


def test_overview_status_filter(api_client: TestClient) -> None:
    _create_fact(api_client, customer_id=1, project_id=10, status="confirmed", title="confirmed fact")
    _create_fact(api_client, customer_id=1, project_id=10, status="draft", title="draft fact")

    response = api_client.get("/api/knowledge/facts/overview", params={"status": "confirmed"})
    assert response.status_code == 200
    data = response.json()
    assert data["total_fact_count"] == 1
    c = data["customers"][0]
    assert c["fact_count"] == 1


def test_overview_unassigned_project(api_client: TestClient) -> None:
    _create_fact(api_client, customer_id=1, project_id=None, title="orphan fact")

    response = api_client.get("/api/knowledge/facts/overview")
    assert response.status_code == 200
    data = response.json()
    c = data["customers"][0]
    assert any(p["project_id"] is None for p in c["projects"])
    unassigned = next(p for p in c["projects"] if p["project_id"] is None)
    assert unassigned["project_name"] == "未归项目"


def test_create_fact_inherits_missing_customer_project_from_task(api_client: TestClient) -> None:
    task_resp = api_client.post("/api/tasks", json={
        "title": "task with fk",
        "customer_id": 34,
        "project_id": 59,
        "source": "web",
        "tags": [],
    })
    assert task_resp.status_code == 201, task_resp.text
    task_id = task_resp.json()["id"]

    fact = _create_fact(api_client, task_id=task_id, title="inherit fk")

    assert fact["task_id"] == task_id
    assert fact["customer_id"] == 34
    assert fact["project_id"] == 59


def test_overview_unassigned_customer(api_client: TestClient) -> None:
    _create_fact(api_client, customer_id=None, project_id=10, title="no customer fact")

    response = api_client.get("/api/knowledge/facts/overview")
    assert response.status_code == 200
    data = response.json()
    assert any(c["customer_id"] is None for c in data["customers"])
    null_c = next(c for c in data["customers"] if c["customer_id"] is None)
    assert null_c["customer_name"] == "未关联客户"


def test_list_facts_project_unassigned(api_client: TestClient) -> None:
    _create_fact(api_client, customer_id=1, project_id=10, title="has project")
    _create_fact(api_client, customer_id=1, project_id=None, title="no project")

    response = api_client.get("/api/facts", params={"customer_id": 1, "project_unassigned": "true"})
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["title"] == "no project"


def test_list_facts_project_unassigned_conflict(api_client: TestClient) -> None:
    response = api_client.get("/api/facts", params={"project_id": 10, "project_unassigned": "true"})
    assert response.status_code == 400


def test_knowledge_preferences_crud(api_client: TestClient) -> None:
    resp = api_client.get("/api/preferences/knowledge")
    assert resp.status_code == 200
    assert resp.json() == {"pinned_customer_ids": [], "customer_order_ids": []}

    resp = api_client.patch("/api/preferences/knowledge", json={
        "pinned_customer_ids": [3, 1],
        "customer_order_ids": [1, 2],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["pinned_customer_ids"] == [3, 1]
    assert data["customer_order_ids"] == [1, 2]

    resp = api_client.get("/api/preferences/knowledge")
    assert resp.status_code == 200
    assert resp.json() == data


def test_knowledge_preferences_dedup(api_client: TestClient) -> None:
    resp = api_client.patch("/api/preferences/knowledge", json={
        "pinned_customer_ids": [1, 1, 2, 3, 2],
        "customer_order_ids": [3, 3, 1],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["pinned_customer_ids"] == [1, 2, 3]
    assert data["customer_order_ids"] == [3, 1]
