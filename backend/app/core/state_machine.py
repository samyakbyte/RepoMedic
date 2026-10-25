"""Session state machine: the single source of truth for session state.

Every transition is appended to the session timeline with a real timestamp.
Illegal transitions raise ApiError (-> HTTP 409).
"""

import os
import threading
from datetime import datetime, timezone
from typing import Optional

from app.config import SESSIONS_DIR
from app.core.workspace import WorkspaceManager
from app.schemas.common import ApiError, SessionState, TimelineEntry
from app.schemas.session import AttemptRecord, SessionDetail, SessionSummary

WORKING_STATES = {
    SessionState.DIAGNOSING,
    SessionState.GENERATING_REPAIR,
    SessionState.APPLYING_PATCH,
    SessionState.VERIFYING,
}

# Allowed transitions: from -> set of allowed to states.
ALLOWED_TRANSITIONS = {
    SessionState.IDLE: {SessionState.DIAGNOSING},
    SessionState.DIAGNOSING: {SessionState.FAILURE_DETECTED, SessionState.IDLE, SessionState.ERROR},
    SessionState.FAILURE_DETECTED: {SessionState.GENERATING_REPAIR},
    SessionState.GENERATING_REPAIR: {SessionState.PATCH_READY, SessionState.ERROR},
    SessionState.PATCH_READY: {SessionState.AWAITING_APPROVAL},
    SessionState.AWAITING_APPROVAL: {SessionState.APPLYING_PATCH, SessionState.FAILURE_DETECTED},
    SessionState.APPLYING_PATCH: {SessionState.VERIFYING, SessionState.ERROR},
    SessionState.VERIFYING: {SessionState.REPAIR_VERIFIED, SessionState.REPAIR_FAILED, SessionState.ERROR},
    SessionState.REPAIR_FAILED: {SessionState.GENERATING_REPAIR, SessionState.IDLE},
    SessionState.REPAIR_VERIFIED: {SessionState.IDLE},
    SessionState.ERROR: {SessionState.IDLE},
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SessionStore:
    """In-memory registry of sessions with per-session disk persistence.

    Uses a reentrant lock per session so that methods like transition() can
    call get() while already holding the lock.
    """

    def __init__(self, workspace_manager: WorkspaceManager):
        self.workspace_manager = workspace_manager
        self._sessions: dict = {}
        self._locks: dict = {}

    def _lock_for(self, session_id: str):
        if session_id not in self._locks:
            self._locks[session_id] = threading.RLock()
        return self._locks[session_id]

    def get(self, session_id: str) -> SessionDetail:
        with self._lock_for(session_id):
            if session_id in self._sessions:
                return self._sessions[session_id]
            disk = SESSIONS_DIR / session_id / "session.json"
            if disk.exists():
                data = self._load_json(disk)
                session = SessionDetail(**data)
            else:
                raise ApiError("SESSION_NOT_FOUND", f"Session not found: {session_id}", state=None, status_code=404)
            self._sessions[session_id] = session
            return session

    def save(self, session: SessionDetail) -> None:
        disk = SESSIONS_DIR / session.id / "session.json"
        disk.parent.mkdir(parents=True, exist_ok=True)
        tmp = disk.with_name(disk.name + ".tmp")
        tmp.write_text(session.model_dump_json(indent=2), encoding="utf-8")
        os.replace(tmp, disk)
        self._sessions[session.id] = session

    def create(self, session_id: str, project_id: str) -> SessionDetail:
        now = _now()
        session = SessionDetail(
            id=session_id,
            project_id=project_id,
            state=SessionState.IDLE,
            attempt=0,
            max_attempts=2,
            created_at=now,
            updated_at=now,
        )
        self.save(session)
        return session

    def transition(
        self,
        session_id: str,
        new_state: SessionState,
        note: Optional[str] = None,
    ) -> SessionDetail:
        with self._lock_for(session_id):
            session = self.get(session_id)
            allowed = ALLOWED_TRANSITIONS.get(session.state, set())
            if new_state not in allowed:
                raise ApiError(
                    "STATE_CONFLICT",
                    f"Illegal transition {session.state} -> {new_state}",
                    state=session.state.value,
                    status_code=409,
                )
            session.state = new_state
            session.updated_at = _now()
            session.timeline.append(TimelineEntry(state=new_state, at=session.updated_at, note=note))
            self.save(session)
            return session

    def set_diagnostics(self, session_id: str, diagnostics) -> SessionDetail:
        with self._lock_for(session_id):
            session = self.get(session_id)
            session.diagnostics_before = diagnostics
            session.updated_at = _now()
            self.save(session)
            return session

    def add_attempt(self, session_id: str, attempt: AttemptRecord) -> SessionDetail:
        with self._lock_for(session_id):
            session = self.get(session_id)
            session.attempt = attempt.n
            session.attempts.append(attempt)
            session.updated_at = _now()
            self.save(session)
            return session

    def set_verdict(self, session_id: str, verdict: Optional[str]) -> SessionDetail:
        with self._lock_for(session_id):
            session = self.get(session_id)
            session.verdict = verdict
            session.updated_at = _now()
            self.save(session)
            return session

    def summary(self, session: SessionDetail) -> SessionSummary:
        return SessionSummary(
            id=session.id,
            project_id=session.project_id,
            state=session.state,
            attempt=session.attempt,
            max_attempts=session.max_attempts,
            verdict=session.verdict,
            created_at=session.created_at,
            updated_at=session.updated_at,
        )

    def list_sessions(self) -> list:
        summaries = []
        if not SESSIONS_DIR.exists():
            return summaries
        for entry in sorted(SESSIONS_DIR.iterdir(), key=lambda p: p.name, reverse=True):
            if not entry.is_dir():
                continue
            disk = entry / "session.json"
            if not disk.exists():
                continue
            try:
                data = self._load_json(disk)
                summaries.append(SessionSummary(**data))
            except Exception:
                continue
        return summaries

    @staticmethod
    def _load_json(path):
        import json

        return json.loads(path.read_text(encoding="utf-8"))
