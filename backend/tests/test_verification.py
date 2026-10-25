"""Verification verdict logic: pass, still failing, regression, syntax error, timeout."""

from pathlib import Path

import pytest

from app.core.verification import Verifier
from app.core.workspace import WorkspaceManager

DEMO_DIR = Path(__file__).resolve().parent.parent.parent / "demo-projects"


def _make_proj(tmp_path, source: str, test: str):
    proj = tmp_path / "proj"
    (proj / "src").mkdir()
    (proj / "src" / "mod.py").write_text(source, encoding="utf-8")
    (proj / "tests").mkdir()
    (proj / "tests" / "test_mod.py").write_text(test, encoding="utf-8")
    return proj


def test_verify_all_passing_verified(tmp_path):
    proj = _make_proj(
        tmp_path,
        "def add(a, b):\n    return a + b\n",
        "from mod import add\ndef test_add():\n    assert add(2, 3) == 5\n",
    )
    verdict = Verifier().verify(str(proj), ["pytest", "-q", "tests"], [], [])
    assert verdict.verdict == "REPAIR_VERIFIED"
    assert verdict.reason is None
    assert verdict.failed == 0


def test_verify_still_failing(tmp_path):
    proj = _make_proj(
        tmp_path,
        "def add(a, b):\n    return a - b\n",
        "from mod import add\ndef test_add():\n    assert add(2, 3) == 5\n",
    )
    verdict = Verifier().verify(str(proj), ["pytest", "-q", "tests"], ["tests/test_mod.py::test_add"], [])
    assert verdict.verdict == "REPAIR_FAILED"
    assert verdict.reason == "ORIGINAL_STILL_FAILING"


def test_verify_regression_detected(tmp_path):
    proj = _make_proj(
        tmp_path,
        "def add(a, b):\n    return a + b\n",
        "from mod import add\ndef test_add():\n    assert add(2, 3) == 5\n\ndef test_sub():\n    assert True\n",
    )
    # Patch breaks test_sub which passed before
    (proj / "src" / "mod.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    (proj / "tests" / "test_mod.py").write_text(
        "from mod import add\ndef test_add():\n    assert add(2, 3) == 5\n\ndef test_sub():\n    assert False\n", encoding="utf-8"
    )
    verdict = Verifier().verify(
        str(proj), ["pytest", "-q", "tests"], [], ["tests/test_mod.py::test_add", "tests/test_mod.py::test_sub"]
    )
    assert verdict.verdict == "REPAIR_FAILED"
    assert verdict.reason == "REGRESSION"
    assert "tests/test_mod.py::test_sub" in verdict.regressions


def test_verify_syntax_error_state(tmp_path):
    proj = _make_proj(
        tmp_path,
        "def add(a, b):\n    return a +\n",
        "from mod import add\ndef test_add():\n    assert add(2, 3) == 5\n",
    )
    verdict = Verifier().verify(str(proj), ["pytest", "-q", "tests"], [], [])
    assert verdict.verdict == "REPAIR_FAILED"
    assert verdict.reason == "SYNTAX_ERROR"
