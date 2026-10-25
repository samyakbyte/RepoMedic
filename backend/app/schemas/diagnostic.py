"""Diagnostics models: pytest results parsed from JUnit XML."""

from typing import Optional

from pydantic import BaseModel, Field


class Failure(BaseModel):
    test_id: str = Field(..., description='e.g. "tests/test_calc.py::test_apply_discount_partial"')
    file: Optional[str] = None
    line: Optional[int] = None
    message: str = ""
    traceback: Optional[str] = None


class DiagnosticsResult(BaseModel):
    exit_code: int
    passed: int = 0
    failed: int = 0
    errors: int = 0
    skipped: int = 0
    total: int = 0
    duration_s: float = 0.0
    failures: list[Failure] = Field(default_factory=list)
    passing_tests: list[str] = Field(default_factory=list)
    raw_output: str = ""
    timeout_occurred: bool = False
    # One of: None | "SYNTAX_ERROR" | "NO_TESTS_COLLECTED" | "TIMEOUT" | "INTERNAL"
    error_type: Optional[str] = None

    @property
    def has_failures(self) -> bool:
        return self.failed > 0 or self.errors > 0 or self.error_type is not None
