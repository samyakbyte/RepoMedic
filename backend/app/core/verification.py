"""Verification: rerun pytest after a patch and reach an honest verdict."""

from pathlib import Path
from typing import Optional

from app.config import PYTEST_TIMEOUT_S
from app.core.diagnostics import run_pytest
from app.schemas.session import VerificationResult


class Verifier:
    def __init__(self, timeout_s: float = PYTEST_TIMEOUT_S):
        self.timeout_s = timeout_s

    def verify(
        self,
        workspace_root: str | Path,
        command: list[str],
        previously_failing: list[str],
        previously_passing: list[str],
    ) -> VerificationResult:
        result = run_pytest(workspace_root, command, timeout_s=self.timeout_s)

        after_failing_names: set[str] = {f.test_id for f in result.failures}

        verdict = "REPAIR_FAILED"
        reason: Optional[str] = None
        regressions: list[str] = []
        originally_failing_now_passing: list[str] = []

        if result.timeout_occurred or result.error_type == "TIMEOUT":
            reason = "VERIFY_TIMEOUT"
        elif result.error_type == "SYNTAX_ERROR":
            reason = "SYNTAX_ERROR"
        elif result.exit_code != 0:
            reason = f"EXIT_CODE_{result.exit_code}"
        elif result.failed > 0 or result.errors > 0:
            still_failing = sorted(set(previously_failing) & after_failing_names)
            regressed = sorted(after_failing_names - set(previously_failing))
            if still_failing:
                reason = "ORIGINAL_STILL_FAILING"
            elif regressed:
                reason = "REGRESSION"
                regressions = regressed
            else:
                reason = "TESTS_STILL_FAILING"
        else:
            verdict = "REPAIR_VERIFIED"
            reason = None
            originally_failing_now_passing = sorted(set(previously_failing) - after_failing_names)

        return VerificationResult(
            verdict=verdict,
            reason=reason,
            passed=result.passed,
            failed=result.failed,
            errors=result.errors,
            total=result.total,
            duration_s=result.duration_s,
            originally_failing_now_passing=originally_failing_now_passing,
            regressions=regressions,
            timeout_occurred=bool(result.timeout_occurred),
            raw_output=result.raw_output,
        )
