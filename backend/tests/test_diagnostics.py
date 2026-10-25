"""Diagnostics: real pytest runs, JUnit parsing, timeouts, syntax errors."""

import xml.etree.ElementTree as ET
from pathlib import Path

from app.core.diagnostics import _parse_junit, run_pytest
from app.core.workspace import WorkspaceManager

DEMO_DIR = Path(__file__).resolve().parent.parent.parent / "demo-projects"


def _junit_xml(tmp_path, suite_xml):
    root = ET.fromstring(suite_xml)
    path = tmp_path / "junit.xml"
    ET.ElementTree(root).write(path)
    return path


def test_parse_junit_counts_and_failures(tmp_path):
    from app.schemas.diagnostic import DiagnosticsResult

    xml = '''<testsuite name="tests" tests="3" failures="1" errors="0" skipped="0" time="0.5">
      <testcase name="test_ok" classname="test_calc" file="tests/test_calc.py" line="3" time="0.01"/>
      <testcase name="test_bad" classname="test_calc" file="tests/test_calc.py" line="10" time="0.02">
        <failure message="assert 190.0 == 180.0" type="AssertionError">traceback line 1\ntraceback line 2</failure>
      </testcase>
      <testcase name="test_err" classname="test_calc" file="tests/test_calc.py" line="20" time="0.01">
        <error message="ModuleNotFoundError" type="ModuleNotFoundError">error traceback</error>
      </testcase>
    </testsuite>'''
    path = _junit_xml(tmp_path, xml)
    result = DiagnosticsResult(exit_code=1)
    _parse_junit(path, result)
    assert result.passed == 1
    assert result.failed == 1
    assert result.errors == 1
    assert result.total == 3
    assert result.duration_s == 0.5
    assert len(result.failures) == 2
    assert result.failures[0].test_id == "tests/test_calc.py::test_bad"
    assert result.failures[0].message == "assert 190.0 == 180.0"
    assert result.failures[0].line == 10
    assert result.passing_tests == ["tests/test_calc.py::test_ok"]


def test_running_passing_project(tmp_path):
    proj = tmp_path / "proj"
    (proj / "src").mkdir(parents=True, exist_ok=True)
    (proj / "src" / "mod.py").write_text("def add(a, b): return a + b\n", encoding="utf-8")
    (proj / "tests").mkdir(parents=True, exist_ok=True)
    (proj / "tests" / "test_mod.py").write_text(
        "from mod import add\ndef test_add(): assert add(2, 3) == 5\n", encoding="utf-8"
    )
    result = run_pytest(proj, ["pytest", "-q", "tests"])
    assert result.error_type is None, result.raw_output
    assert result.failed == 0
    assert result.errors == 0
    assert result.passed >= 1
    assert result.exit_code == 0


def test_running_failing_project(tmp_path):
    mgr = WorkspaceManager(DEMO_DIR)
    ws = mgr.create_workspace("session-diag-fail", "calculator-bug")
    try:
        result = run_pytest(ws, ["pytest", "-q", "tests"])
        assert result.failed >= 1, result.raw_output
        assert result.errors == 0
        assert result.error_type is None
        assert result.exit_code == 1
        assert any("test_apply_discount_partial" in f.test_id for f in result.failures)
        assert any("180" in f.message for f in result.failures)
    finally:
        mgr.cleanup("session-diag-fail")


def test_syntax_error_is_error_state(tmp_path):
    proj = tmp_path / "proj"
    (proj / "src").mkdir(parents=True, exist_ok=True)
    (proj / "src" / "broken.py").write_text("def add(a, b): return a +\n", encoding="utf-8")
    (proj / "tests").mkdir(parents=True, exist_ok=True)
    (proj / "tests" / "test_broken.py").write_text("from broken import add\ndef test_x(): assert add(1, 2) == 3\n", encoding="utf-8")
    result = run_pytest(proj, ["pytest", "-q", "tests"])
    assert result.error_type == "SYNTAX_ERROR", (result.error_type, result.raw_output)


def test_timeout_is_captured(tmp_path):
    proj = tmp_path / "proj"
    (proj / "tests").mkdir(parents=True, exist_ok=True)
    (proj / "tests" / "test_slow.py").write_text(
        "import time\ndef test_slow():\n    time.sleep(10)\n", encoding="utf-8"
    )
    result = run_pytest(proj, ["pytest", "-q", "tests"], timeout_s=1.0)
    assert result.timeout_occurred is True
    assert result.error_type == "TIMEOUT", result.error_type


def test_no_tests_collected(tmp_path):
    proj = tmp_path / "proj"
    (proj / "tests").mkdir(parents=True, exist_ok=True)
    result = run_pytest(proj, ["pytest", "-q", "tests"])
    assert result.error_type == "NO_TESTS_COLLECTED", result.error_type
    assert result.exit_code == 5
