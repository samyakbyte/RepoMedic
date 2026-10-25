"""Shared Pydantic models and constants used across schemas."""

import enum
from datetime import datetime
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel


def new_session_id() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid4().hex[:6]


class SessionState(str, enum.Enum):
    IDLE = "IDLE"
    DIAGNOSING = "DIAGNOSING"
    FAILURE_DETECTED = "FAILURE_DETECTED"
    GENERATING_REPAIR = "GENERATING_REPAIR"
    PATCH_READY = "PATCH_READY"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    APPLYING_PATCH = "APPLYING_PATCH"
    VERIFYING = "VERIFYING"
    REPAIR_VERIFIED = "REPAIR_VERIFIED"
    REPAIR_FAILED = "REPAIR_FAILED"
    ERROR = "ERROR"


WORKING_STATES = {
    SessionState.DIAGNOSING,
    SessionState.GENERATING_REPAIR,
    SessionState.APPLYING_PATCH,
    SessionState.VERIFYING,
}

VERDICT_VERIFIED = "REPAIR_VERIFIED"
VERDICT_FAILED = "REPAIR_FAILED"


class TimelineEntry(BaseModel):
    state: SessionState
    at: str
    note: Optional[str] = None


class ErrorBody(BaseModel):
    code: str
    message: str
    hint: Optional[str] = None
    state: Optional[str] = None


class ErrorResponse(BaseModel):
    error: ErrorBody

    def model_dump_api(self) -> dict:
        return self.model_dump()


class ApiError(Exception):
    """Raised internally to produce a consistent API error body."""

    def __init__(
        self,
        code: str,
        message: str,
        hint: Optional[str] = None,
        state: Optional[str] = None,
        status_code: int = 400,
    ):
        self.code = code
        self.message = message
        self.hint = hint
        self.state = state
        self.status_code = status_code
        super().__init__(message)
