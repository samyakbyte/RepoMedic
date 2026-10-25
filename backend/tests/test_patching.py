"""Patch validation, diff generation, apply, and rollback integrity."""

from pathlib import Path

import pytest
from pydantic import TypeAdapter

from app.core.patching import apply_patch, generate_diff, rollback_patch, validate_patch
from app.schemas.patch import PatchValidationResult, RepairProposal

WORKSPACE_SESSION = "session-patch-test"


def _setup_workspace_file(ws: Path, rel: str, text: str) -> None:
    p = ws / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _teardown_workspace(ws: Path) -> None:
    import shutil

    shutil.rmtree(ws, ignore_errors=True)


def _proposal(old, new, target="src/calc.py"):
    return RepairProposal(
        root_cause="test",
        target_file=target,
        old_snippet=old,
        new_snippet=new,
        explanation="test explanation",
        expected_outcome="test outcome",
    )


def _noop_proposal():
    return TypeAdapter(RepairProposal).validate_python(
        {
            "root_cause": "test",
            "target_file": "src/calc.py",
            "old_snippet": "x = 1",
            "new_snippet": "x = 1",
            "explanation": "x",
            "expected_outcome": "y",
        },
        strict=False,
    )


def test_validate_happy_path(tmp_path):
    ws = tmp_path / "ws"
    _setup_workspace_file(ws, "src/calc.py", "def apply_discount(price, percent):\n    return price - price * percent\n")
    try:
        result = validate_patch(
            str(ws), "src/calc.py", _proposal("return price - price * percent", "return price - price * percent / 100"), ["src/calc.py"]
        )
        assert result.ok is True
        assert result.codes == []
        assert result.diff is not None and "- price * percent" in result.diff
        assert result.snippet_normalized is False
    finally:
        _teardown_workspace(ws)


def test_validate_snippet_not_found(tmp_path):
    ws = tmp_path / "ws"
    _setup_workspace_file(ws, "src/calc.py", "x = 1\n")
    try:
        result = validate_patch(str(ws), "src/calc.py", _proposal("no such code", "fixed"), ["src/calc.py"])
        assert result.ok is False
        assert "SNIPPET_NOT_FOUND" in result.codes
    finally:
        _teardown_workspace(ws)


def test_validate_snippet_ambiguous(tmp_path):
    ws = tmp_path / "ws"
    _setup_workspace_file(ws, "src/calc.py", "return a\nreturn a\n")
    try:
        result = validate_patch(str(ws), "src/calc.py", _proposal("return a", "return b"), ["src/calc.py"])
        assert result.ok is False
        assert "SNIPPET_AMBIGUOUS" in result.codes
    finally:
        _teardown_workspace(ws)


def test_validate_noop_patch(tmp_path):
    ws = tmp_path / "ws"
    _setup_workspace_file(ws, "src/calc.py", "x = 1\n")
    try:
        result = validate_patch(str(ws), "src/calc.py", _noop_proposal(), ["src/calc.py"])
        assert result.ok is False
        assert "NOOP_PATCH" in result.codes
    finally:
        _teardown_workspace(ws)


def test_validate_syntax_invalid(tmp_path):
    ws = tmp_path / "ws"
    _setup_workspace_file(ws, "src/calc.py", "def add(a, b):\n    return a + b\n")
    try:
        result = validate_patch(str(ws), "src/calc.py", _proposal("return a + b", "return a +"), ["src/calc.py"])
        assert result.ok is False
        assert "SYNTAX_INVALID" in result.codes
    finally:
        _teardown_workspace(ws)


def test_validate_protected_file(tmp_path):
    ws = tmp_path / "ws"
    _setup_workspace_file(ws, "tests/test_calc.py", "def test_x(): pass\n")
    try:
        result = validate_patch(
            str(ws), "tests/test_calc.py", _proposal("pass", "fail", target="tests/test_calc.py"), ["src/calc.py"]
        )
        assert result.ok is False
        assert result.codes[0] in ("PROTECTED_FILE", "TARGET_NOT_ALLOWED")
    finally:
        _teardown_workspace(ws)


def test_validate_file_not_found(tmp_path):
    ws = tmp_path / "ws"
    try:
        result = validate_patch(str(ws), "src/missing.py", _proposal("x", "y", target="src/missing.py"), ["src/missing.py"])
        assert result.ok is False
        assert "FILE_NOT_FOUND" in result.codes
    finally:
        _teardown_workspace(ws)


def test_validate_path_traversal_rejected(tmp_path):
    ws = tmp_path / "ws"
    try:
        result = validate_patch(str(ws), "../../etc/passwd", _proposal("x", "y", target="../../etc/passwd"), [])
        assert result.ok is False
        assert result.codes[0] == "PATH_TRAVERSAL"
    finally:
        _teardown_workspace(ws)


def test_line_ending_normalization_fallback(tmp_path):
    ws = tmp_path / "ws"
    _setup_workspace_file(ws, "src/calc.py", "def f():\r\n    return 1\r\n")
    try:
        result = validate_patch(
            str(ws), "src/calc.py", _proposal("def f():\n    return 1", "def f():\n    return 2"), ["src/calc.py"]
        )
        assert result.ok is True
        assert result.snippet_normalized is True
        patched = (ws / "src" / "calc.py").read_text(encoding="utf-8")  # not applied here; validate only
        assert "return 1" in patched  # validate does not modify the file
    finally:
        _teardown_workspace(ws)


def test_apply_and_rollback_hash_integrity(tmp_path):
    ws = tmp_path / "ws"
    _setup_workspace_file(ws, "src/calc.py", "def f():\n    return 1\n")
    try:
        proposal = _proposal("    return 1", "    return 2")
        validation = validate_patch(str(ws), "src/calc.py", proposal, ["src/calc.py"])
        assert validation.ok
        result = apply_patch(WORKSPACE_SESSION, 1, "src/calc.py", proposal, validation)
        assert result.ok
        assert result.sha_before != result.sha_after

        # The real workspace dir holds the file now.
        real_ws = Path("data/workspaces") / WORKSPACE_SESSION
        patched = (real_ws / "src" / "calc.py").read_text(encoding="utf-8")
        assert "return 2" in patched

        restored = rollback_patch(WORKSPACE_SESSION, 1, "src/calc.py")
        assert restored == result.sha_before
        again = (real_ws / "src" / "calc.py").read_text(encoding="utf-8")
        assert "return 1" in again
    finally:
        import shutil

        shutil.rmtree(Path("data/workspaces") / WORKSPACE_SESSION, ignore_errors=True)
        _teardown_workspace(ws)


def test_generate_diff_shape(tmp_path):
    _setup_workspace_file(tmp_path, "src/calc.py", "a = 1\nb = 2\n")
    diff = generate_diff("a = 1\nb = 2\n", "a = 1\nb = 3\n", "src/calc.py")
    assert "src/calc.py" in diff
    assert "-b = 2" in diff and "+b = 3" in diff
