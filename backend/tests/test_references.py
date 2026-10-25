"""Reference fixes: applied to copies they make all tests pass; never leak into prompts."""

import shutil
from pathlib import Path

import pytest

from app.core.context import ContextBuilder
from app.core.diagnostics import DiagnosticsResult, Failure, run_pytest
from app.core.workspace import WorkspaceManager

DEMO_DIR = Path(__file__).resolve().parent.parent.parent / "demo-projects"
REF_DIR = Path(__file__).resolve().parent.parent.parent / "evaluation" / "references"

PROJECTS = ["calculator-bug", "inventory-bug", "string-utils-bug"]


@pytest.mark.parametrize("project_id", PROJECTS)
def test_reference_fix_makes_all_tests_pass(tmp_path, project_id):
    proj_src = DEMO_DIR / project_id
    ref_src = REF_DIR / project_id / "src"
    work = tmp_path / project_id
    shutil.copytree(proj_src, work, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    for ref_file in ref_src.rglob("*"):
        if ref_file.is_file():
            rel = ref_file.relative_to(ref_src)
            dest = work / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(ref_file.read_text(encoding="utf-8"), encoding="utf-8")
    result = run_pytest(work, ["pytest", "-q", "tests"])
    assert result.error_type is None, result.raw_output
    assert result.failed == 0, result.raw_output
    assert result.errors == 0, result.raw_output
    assert result.passed >= 4, f"expected at least 4 passing tests, got {result.passed}"


def test_reference_content_never_in_prompt(tmp_path):
    mgr = WorkspaceManager(DEMO_DIR)
    ws = mgr.create_workspace("session-ref", "calculator-bug")
    try:
        ref_text = (REF_DIR / "calculator-bug" / "src" / "calc.py").read_text(encoding="utf-8")
        secret = "price * percent / 100"
        assert secret in ref_text
        diag = DiagnosticsResult(
            exit_code=1, passed=5, failed=1, errors=0, total=6,
            failures=[Failure(
                test_id="tests/test_calc.py::test_apply_discount_partial",
                file="tests/test_calc.py", line=14,
                message="assert -1800.0 == 180.0",
            )],
        )
        builder = ContextBuilder(max_chars=6000)
        ctx = builder.build(
            str(ws), diag, "tests/test_calc.py::test_apply_discount_partial",
            "Calculator", "desc",
        )
        assert secret not in ctx, "reference fix leaked into the LLM context"
    finally:
        mgr.cleanup("session-ref")
