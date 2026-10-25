"""API integration tests with FastAPI TestClient (Ollama paths are error-checked only)."""

import asyncio

from fastapi.testclient import TestClient

from app.main import app
from app.api.routers.sessions import _run_diagnose

client = TestClient(app)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"


def test_model_status_ollama_down():
    r = client.get("/api/model/status")
    assert r.status_code == 200
    body = r.json()
    assert body["ollama_reachable"] is False
    assert body["model_available"] is False
    assert body["hint"]
    assert "ollama" in body["hint"].lower()


def test_projects():
    r = client.get("/api/projects")
    assert r.status_code == 200
    ids = [p["id"] for p in r.json()]
    assert set(ids) == {"calculator-bug", "inventory-bug", "string-utils-bug"}


def test_create_session_unknown_project_error_shape():
    r = client.post("/api/sessions", json={"project_id": "nope-such-project"})
    assert r.status_code == 400
    body = r.json()
    assert set(body.keys()) == {"error"}
    err = body["error"]
    assert err["code"] == "UNKNOWN_PROJECT"
    assert err["message"]
    assert err["hint"]


def test_full_session_flow_without_ollama():
    r = client.post("/api/sessions", json={"project_id": "calculator-bug"})
    assert r.status_code == 201
    sid = r.json()["id"]
    assert r.json()["state"] == "IDLE"

    r = client.get(f"/api/sessions/{sid}")
    assert r.json()["state"] == "IDLE"

    # Diagnose (202), then drive the background task directly so the test is deterministic.
    r = client.post(f"/api/sessions/{sid}/diagnose")
    assert r.status_code == 202
    asyncio.run(_run_diagnose(sid))

    r = client.get(f"/api/sessions/{sid}")
    s = r.json()
    assert s["state"] == "FAILURE_DETECTED", s
    assert s["diagnostics_before"]["failed"] >= 1
    assert len(s["timeline"]) >= 2

    # No patch yet.
    r = client.get(f"/api/sessions/{sid}/patch")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NO_PATCH"

    # Repair triggers real Ollama (down) -> ERROR state; that path is exercised here.
    r = client.post(f"/api/sessions/{sid}/repair")
    assert r.status_code == 202

    # Approving outside AWAITING_APPROVAL -> 409 with consistent error body.
    r = client.post(f"/api/sessions/{sid}/approve")
    assert r.status_code == 409
    body = r.json()
    assert body["error"]["code"] == "STATE_CONFLICT"
    assert body["error"]["hint"]
    assert body["error"]["state"]

    # Reset puts us back in IDLE; repair from IDLE is an illegal transition -> 409.
    r = client.post(f"/api/sessions/{sid}/reset")
    assert r.status_code == 200
    assert client.get(f"/api/sessions/{sid}").json()["state"] == "IDLE"
    r = client.post(f"/api/sessions/{sid}/repair")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "STATE_CONFLICT"

    # Session appears in history.
    r = client.get("/api/sessions")
    assert r.status_code == 200
    assert any(x["id"] == sid for x in r.json())
