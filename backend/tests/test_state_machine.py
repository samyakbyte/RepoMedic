"""State machine: legal and illegal transitions, timeline records."""

import os
import tempfile
from pathlib import Path

import pytest

import app.core.state_machine as sm
from app.core.state_machine import SessionStore, SessionState
from app.core.workspace import WorkspaceManager
from app.schemas.common import ApiError


@pytest.fixture
def store(tmp_path, monkeypatch):
    tmp = tmp_path / "sessions"
    monkeypatch.setattr(sm, "SESSIONS_DIR", tmp)
    tmp.mkdir(parents=True, exist_ok=True)
    return SessionStore(WorkspaceManager(Path(__file__).resolve().parent.parent.parent / "demo-projects"))


def test_legal_transition_chain(store):
    session = store.create("s1", "calculator-bug")
    assert session.state == SessionState.IDLE

    session = store.transition("s1", SessionState.DIAGNOSING, "running pytest")
    assert session.state == SessionState.DIAGNOSING
    assert len(session.timeline) == 1
    assert session.timeline[0].note == "running pytest"
    assert "T" in session.timeline[0].at  # ISO timestamp

    session = store.transition("s1", SessionState.FAILURE_DETECTED, "1 failing")
    session = store.transition("s1", SessionState.GENERATING_REPAIR, "attempt 1")
    session = store.transition("s1", SessionState.PATCH_READY, "validated")
    session = store.transition("s1", SessionState.AWAITING_APPROVAL, "waiting")
    session = store.transition("s1", SessionState.APPLYING_PATCH, "approved")
    session = store.transition("s1", SessionState.VERIFYING, "verifying")
    session = store.transition("s1", SessionState.REPAIR_VERIFIED, "done")
    session = store.transition("s1", SessionState.IDLE, "new session")
    assert session.state == SessionState.IDLE
    assert len(session.timeline) == 9


def test_illegal_transition_returns_409(store):
    store.create("s2", "inventory-bug")
    with pytest.raises(ApiError) as exc:
        store.transition("s2", SessionState.REPAIR_VERIFIED, "nope")
    assert exc.value.code == "STATE_CONFLICT"
    assert exc.value.status_code == 409
    assert exc.value.state == SessionState.IDLE.value

    with pytest.raises(ApiError) as exc:
        store.transition("s2", SessionState.GENERATING_REPAIR, "nope")
    assert exc.value.status_code == 409


def test_repair_failed_allows_retry_then_idle(store):
    store.create("s3", "string-utils-bug")
    store.transition("s3", SessionState.DIAGNOSING, "x")
    store.transition("s3", SessionState.FAILURE_DETECTED, "x")
    store.transition("s3", SessionState.GENERATING_REPAIR, "x")
    store.transition("s3", SessionState.PATCH_READY, "x")
    store.transition("s3", SessionState.AWAITING_APPROVAL, "x")
    store.transition("s3", SessionState.APPLYING_PATCH, "x")
    store.transition("s3", SessionState.VERIFYING, "x")
    store.transition("s3", SessionState.REPAIR_FAILED, "first attempt failed")
    store.transition("s3", SessionState.GENERATING_REPAIR, "attempt 2")
    store.transition("s3", SessionState.PATCH_READY, "x")
    store.transition("s3", SessionState.AWAITING_APPROVAL, "x")
    store.transition("s3", SessionState.APPLYING_PATCH, "x")
    store.transition("s3", SessionState.VERIFYING, "x")
    store.transition("s3", SessionState.REPAIR_FAILED, "second attempt failed")
    store.transition("s3", SessionState.IDLE, "reset")
    assert store.get("s3").state == SessionState.IDLE


def test_error_resets_to_idle(store):
    store.create("s4", "calculator-bug")
    store.transition("s4", SessionState.DIAGNOSING, "x")
    store.transition("s4", SessionState.ERROR, "boom")
    store.transition("s4", SessionState.IDLE, "reset after error")
    assert store.get("s4").state == SessionState.IDLE
