"""Session-related Pydantic models."""

from typing import Optional

from pydantic import BaseModel, Field

from .common import SessionState, TimelineEntry
from .diagnostic import DiagnosticsResult
from .patch import PatchValidationResult, RepairProposal


class LLMMetrics(BaseModel):
    model: str
    duration_s: float
    prompt_eval_count: Optional[int] = None
    eval_count: Optional[int] = None
    eval_duration_ns: Optional[int] = None
    total_duration_ns: Optional[int] = None
    load_duration_ns: Optional[int] = None
    tokens_per_second: Optional[float] = None


class VerificationResult(BaseModel):
    verdict: str  # REPAIR_VERIFIED | REPAIR_FAILED
    reason: Optional[str] = None
    passed: int = 0
    failed: int = 0
    errors: int = 0
    total: int = 0
    duration_s: float = 0.0
    originally_failing_now_passing: list[str] = Field(default_factory=list)
    regressions: list[str] = Field(default_factory=list)
    timeout_occurred: bool = False
    raw_output: str = ""


class AttemptRecord(BaseModel):
    n: int
    patch: RepairProposal
    validation: PatchValidationResult
    llm: LLMMetrics
    approved: Optional[bool] = None
    rejected_reason: Optional[str] = None
    verification: Optional[VerificationResult] = None


class SessionSummary(BaseModel):
    id: str
    project_id: str
    state: SessionState
    attempt: int
    max_attempts: int
    verdict: Optional[str] = None
    created_at: str
    updated_at: str


class SessionDetail(SessionSummary):
    project_name: Optional[str] = None
    diagnostics_before: Optional[DiagnosticsResult] = None
    attempts: list[AttemptRecord] = Field(default_factory=list)
    timeline: list[TimelineEntry] = Field(default_factory=list)
    report_path: Optional[str] = None
