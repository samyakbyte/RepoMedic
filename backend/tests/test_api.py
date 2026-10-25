"""API integration tests with FastAPI TestClient (Ollama down + mocked Ollama E2E)."""

from fastapi.testclient import TestClient

import app.api.routers.sessions as sessions_router
from app.core.llm import LLMResult
from app.main import app
from app.schemas.patch import RepairProposal

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

    # Diagnose runs in BackgroundTasks and transitions to FAILURE_DETECTED.
    r = client.post(f"/api/sessions/{sid}/diagnose")
    assert r.status_code == 202

    r = client.get(f"/api/sessions/{sid}")
    s = r.json()
    assert s["state"] == "FAILURE_DETECTED", s
    assert s["diagnostics_before"]["failed"] >= 1
    assert len(s["timeline"]) >= 2

    # No patch yet.
    r = client.get(f"/api/sessions/{sid}/patch")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NO_PATCH"

    # Repair triggers real Ollama (down) -> ERROR state.
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


def test_full_repair_approve_verify_rollback_with_mocked_ollama(monkeypatch):
    r = client.post("/api/sessions", json={"project_id": "calculator-bug"})
    assert r.status_code == 201
    sid = r.json()["id"]

    files_resp = client.get(f"/api/sessions/{sid}/files")
    assert files_resp.status_code == 200
    calc_src = files_resp.json()["files"]["src/calc.py"]
    old_line = [ln.strip() for ln in calc_src.splitlines() if "percent" in ln and "return" in ln][0]

    def fake_generate_exact(_context: str) -> LLMResult:
        assert "def apply_discount" in _context
        return LLMResult(
            proposal=RepairProposal(
                root_cause="percent was multiplied directly instead of dividing by 100",
                target_file="src/calc.py",
                old_snippet=old_line,
                new_snippet="return round(price * (1 - percent / 100), 2)",
                explanation="Divide percent by 100 when computing discount.",
                expected_outcome="All calculator tests pass.",
            ),
            model="qwen2.5-coder:1.5b",
            duration_s=0.42,
            prompt_eval_count=200,
            eval_count=80,
            eval_duration_ns=400_000_000,
            total_duration_ns=420_000_000,
            load_duration_ns=10_000_000,
        )

    monkeypatch.setattr(sessions_router.llm_client, "generate_repair", fake_generate_exact)

    assert client.post(f"/api/sessions/{sid}/diagnose").status_code == 202
    assert client.get(f"/api/sessions/{sid}").json()["state"] == "FAILURE_DETECTED"

    assert client.post(f"/api/sessions/{sid}/repair").status_code == 202
    s = client.get(f"/api/sessions/{sid}").json()
    assert s["state"] == "AWAITING_APPROVAL", s

    patch_resp = client.get(f"/api/sessions/{sid}/patch")
    assert patch_resp.status_code == 200
    assert patch_resp.json()["validation"]["ok"] is True

    assert client.post(f"/api/sessions/{sid}/approve").status_code == 202
    s = client.get(f"/api/sessions/{sid}").json()
    assert s["state"] == "REPAIR_VERIFIED", s
    assert s["verdict"] == "REPAIR_VERIFIED"

    rep_md = client.get(f"/api/sessions/{sid}/report?format=md")
    assert rep_md.status_code == 200
    assert "REPAIR_VERIFIED" in rep_md.text

    rb = client.post(f"/api/sessions/{sid}/rollback")
    assert rb.status_code == 200
    assert client.get(f"/api/sessions/{sid}").json()["state"] == "FAILURE_DETECTED"
