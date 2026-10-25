"""Context builder: bounds, exclusions, retry feedback."""

from pathlib import Path

from app.core.context import ContextBuilder
from app.core.diagnostics import DiagnosticsResult, Failure
from app.core.workspace import WorkspaceManager

DEMO_DIR = Path(__file__).resolve().parent.parent.parent / "demo-projects"


def _diag(failed=1):
    return DiagnosticsResult(
        exit_code=1,
        passed=4,
        failed=failed,
        errors=0,
        total=4 + failed,
        duration_s=0.3,
        failures=[
            Failure(
                test_id="tests/test_calc.py::test_apply_discount_partial",
                file="tests/test_calc.py",
                line=14,
                message="assert -1800.0 == 180.0",
                traceback="Traceback (most recent call last):\n  File \"tests/test_calc.py\", line 14, in test_apply_discount_partial\n    assert apply_discount(200, 10) == 180\nE   assert -1800.0 == 180.0",
            )
        ],
        passing_tests=[
            "tests/test_calc.py::test_add",
            "tests/test_calc.py::test_subtract",
        ],
    )


def test_context_contains_failure_and_source(tmp_path):
    mgr = WorkspaceManager(DEMO_DIR)
    ws = mgr.create_workspace("session-ctx", "calculator-bug")
    try:
        builder = ContextBuilder(max_charts := 6000)  # noqa: F841
        builder = ContextBuilder(max_chars=6000)
        ctx = builder.build(
            str(ws), _diag(), "tests/test_calc.py::test_apply_discount_partial",
            "Calculator", "desc",
        )
        assert "test_apply_discount_partial" in ctx
        assert "assert -1800.0 == 180.0" in ctx
        assert "apply_discount" in ctx
        assert "def apply_discount" in ctx
        assert "price - price * percent" in ctx
    finally:
        mgr.cleanup("session-ctx")


def test_context_respects_char_bound(tmp_path):
    builder = ContextBuilder(max_chars=200)
    ctx = builder.build(
        str(tmp_path), _diag(), "tests/test_calc.py::test_apply_discount_partial",
        "Calculator", "desc",
    )
    assert len(ctx) <= 200 + 50  # small slack for the truncation marker
    assert ctx.endswith("...[context truncated by RepoMedic]...") or len(ctx) <= 200


def test_retry_feedback_included_in_context(tmp_path):
    builder = ContextBuilder(max_chars=6000)
    ctx = builder.build(
        str(tmp_path), _diag(), "tests/test_calc.py::test_apply_discount_partial",
        "Calculator", "desc",
        previous_attempt={"target_file": "src/calc.py", "old_snippet": "return price - price * percent",
                          "new_snippet": "return price - price * percent / 100",
                          "explanation": "divide by 100"},
        previous_verification={"verdict": "REPAIR_FAILED", "reason": "ORIGINAL_STILL_FAILING",
                               "regressions": [], "originally_failing_now_passing": [],
                               "raw_output": "still failing: assert ..."},
    )
    assert "PREVIOUS ATTEMPT" in ctx
    assert "ORIGINAL_STILL_FAILING" in ctx


def test_evaluation_references_never_in_context(tmp_path):
    # The builder only reads workspace files; reference solutions outside the
    # workspace must never leak into the context.
    (tmp_path / "evaluation").mkdir()
    (tmp_path / "evaluation" / "references").mkdir()
    (tmp_path / "evaluation" / "references" / "calculator-bug").mkdir()
    (tmp_path / "evaluation" / "references" / "calculator-bug" / "src").mkdir()
    (tmp_path / "evaluation" / "references" / "calculator-bug" / "src" / "calc.py").write_text(
        "SECRET_REFERENCE_FIX_12345\n", encoding="utf-8"
    )
    builder = ContextBuilder(max_chars=6000)
    ctx = builder.build(
        str(tmp_path), _diag(), "tests/test_calc.py::test_apply_discount_partial",
        "Calculator", "desc",
    )
    assert "SECRET_REFERENCE_FIX_12345" not in ctx
