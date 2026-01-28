import json
import pytest
from app.api import create_app

# @pytest.fixture
# def client():
#     app = create_app()
#     app.config["TESTING"] = True
#     return app.test_client()

def _headers(actor_id="m1"):
    return {"Content-Type": "application/json", "X-Actor-Id": actor_id}

# ---------- CREATE ----------
def test_create_task_ok(client):
    resp = client.post(
        "/api/tasks",
        headers=_headers("m1"),
        data=json.dumps({"title": "Feature A", "description": "...", "priority": "HIGH"}),
    )
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["title"] == "Feature A"
    assert body["priority"] == "HIGH"
    assert body["owner_id"] == "m1"
    assert body["status"] == "NEW"
    assert "id" in body

def test_create_task_missing_actor_header_400(client):
    resp = client.post(
        "/api/tasks",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"title": "X"}),
    )
    assert resp.status_code == 400
    assert "Missing X-Actor-Id" in resp.get_json()["message"]

def test_create_task_unknown_priority_400(client):
    resp = client.post(
        "/api/tasks",
        headers=_headers("m1"),
        data=json.dumps({"title": "X", "priority": "ULTRA"}),
    )
    assert resp.status_code == 400
    assert resp.get_json()["message"] == "Unknown priority"

# ---------- ASSIGN + STATUS FLOW ----------
def test_assign_and_status_flow(client):
    r1 = client.post("/api/tasks", headers=_headers("m1"), data=json.dumps({"title": "Flow"}))
    tid = r1.get_json()["id"]

    r2 = client.post(f"/api/tasks/{tid}/assign", headers=_headers("m1"),
                     data=json.dumps({"assignee_id": "u1"}))
    assert r2.status_code == 200
    assert r2.get_json()["assignee_id"] == "u1"

    r3 = client.post(f"/api/tasks/{tid}/status", headers=_headers("u1"),
                     data=json.dumps({"new_status": "IN_PROGRESS"}))
    assert r3.status_code == 200
    assert r3.get_json()["status"] == "IN_PROGRESS"

# ---------- LIST ----------
def test_list_with_filters(client):
    a = client.post("/api/tasks", headers=_headers("u1"), data=json.dumps({"title": "T1"})).get_json()
    b = client.post("/api/tasks", headers=_headers("u1"), data=json.dumps({"title": "T2", "priority": "HIGH"})).get_json()
    client.post(f"/api/tasks/{b['id']}/status", headers=_headers("u1"),
                data=json.dumps({"new_status": "IN_PROGRESS"}))

    r_status = client.get("/api/tasks?status=IN_PROGRESS", headers=_headers("u1"))
    assert {t["id"] for t in r_status.get_json()} == {b["id"]}

    r_prio = client.get("/api/tasks?priority=HIGH", headers=_headers("u1"))
    assert {t["id"] for t in r_prio.get_json()} == {b["id"]}

# ---------- UPDATE ----------
def test_update_title_and_priority(client):
    t = client.post("/api/tasks", headers=_headers("u1"), data=json.dumps({"title": "Old"})).get_json()
    r = client.patch(f"/api/tasks/{t['id']}", headers=_headers("u1"),
                     data=json.dumps({"title": "New", "priority": "HIGH"}))
    assert r.status_code == 200
    body = r.get_json()
    assert body["title"] == "New"
    assert body["priority"] == "HIGH"

def test_update_missing_actor_or_task_400(client):
    t = client.post("/api/tasks", headers=_headers("u1"), data=json.dumps({"title": "A"})).get_json()
    r1 = client.patch(f"/api/tasks/{t['id']}", headers={"Content-Type": "application/json"}, data=json.dumps({"title": "X"}))
    assert r1.status_code == 400
    assert "Missing X-Actor-Id" in r1.get_json()["message"]

    r2 = client.patch("/api/tasks/NOPE", headers=_headers("u1"), data=json.dumps({"title": "X"}))
    assert r2.status_code == 400

# ---------- DELETE ----------
def test_delete_soft_and_idempotent(client):
    t = client.post("/api/tasks", headers=_headers("m1"), data=json.dumps({"title": "Del"})).get_json()
    r1 = client.delete(f"/api/tasks/{t['id']}", headers=_headers("m1"))
    assert r1.status_code == 200
    assert r1.get_json()["is_deleted"] is True

    r2 = client.delete(f"/api/tasks/{t['id']}", headers=_headers("m1"))
    assert r2.status_code == 200
    assert r2.get_json()["is_deleted"] is True

# ---------- EVENTS ----------
def test_events_history_ok(client):
    t = client.post("/api/tasks", headers=_headers("m1"), data=json.dumps({"title": "E"})).get_json()
    client.post(f"/api/tasks/{t['id']}/assign", headers=_headers("m1"),
                data=json.dumps({"assignee_id": "u1"}))
    client.post(f"/api/tasks/{t['id']}/status", headers=_headers("u1"),
                data=json.dumps({"new_status": "IN_PROGRESS"}))

    r = client.get(f"/api/tasks/{t['id']}/events", headers=_headers("u1"))
    kinds = [e["type"] for e in r.get_json()]
    assert "CREATED" in kinds and "ASSIGNED" in kinds and "STATUS_CHANGED" in kinds

def test_events_forbidden_for_unrelated_actor(client):
    t = client.post("/api/tasks", headers=_headers("u1"), data=json.dumps({"title": "Sec"})).get_json()
    r = client.get(f"/api/tasks/{t['id']}/events", headers=_headers("u2"))
    assert r.status_code == 403

# ---------- USERS ----------
def test_create_user_ok(client):
    r = client.post(
        "/api/users",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"id": "u9", "email": "u9@ex.com", "role": "USER", "status": "ACTIVE"}),
    )
    assert r.status_code == 201
    assert r.get_json()["message"] == "User created"

def test_create_user_missing_field_400(client):
    r = client.post(
        "/api/users",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"email": "x@ex.com"}),
    )
    assert r.status_code == 400
    assert "Missing field" in r.get_json()["message"]

# ---------- VALIDATION GAPS ----------
def test_assign_missing_assignee_id_400(client):
    t = client.post("/api/tasks", headers=_headers("m1"), data=json.dumps({"title": "A"})).get_json()
    r = client.post(f"/api/tasks/{t['id']}/assign", headers=_headers("m1"), data=json.dumps({}))
    assert r.status_code == 400
    assert "Missing assignee_id" in r.get_json()["message"]

def test_status_missing_new_status_400(client):
    t = client.post("/api/tasks", headers=_headers("u1"), data=json.dumps({"title": "A"})).get_json()
    r = client.post(f"/api/tasks/{t['id']}/status", headers=_headers("u1"), data=json.dumps({}))
    assert r.status_code == 400
    assert "Missing new_status" in r.get_json()["message"]

# ---------- ERROR HANDLERS ----------
def test_404_handler_unknown_route(client):
    r = client.get("/api/route-that-does-not-exist", headers=_headers("m1"))
    assert r.status_code == 404
    assert r.get_json()["message"] == "Not found"

def test_500_handler_unexpected_exception(client, monkeypatch):
    from src.serwis.task_service import TaskService
    def boom(*args, **kwargs):
        raise RuntimeError("boom")
    monkeypatch.setattr(TaskService, "create_task", boom)

    r = client.post(
        "/api/tasks",
        headers=_headers("m1"),
        data=json.dumps({"title": "X"}),
    )
    assert r.status_code == 500
    assert r.get_json()["message"] == "Internal Server Error"