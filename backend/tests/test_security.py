"""Security tests: path traversal, symlinks, protected files, scrubbed env."""

import os
from pathlib import Path

import pytest

from app.core.security import (
    SecurityError,
    is_patchable,
    resolve_safe_path,
    scrubbed_env,
)


@pytest.fixture
def ws(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "calc.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_calc.py").write_text("def t(): pass\n", encoding="utf-8")
    return tmp_path


def test_resolve_safe_normal(ws):
    resolved = resolve_safe_path(ws, "src/calc.py")
    assert resolved.name == "calc.py"
    assert resolved.parent == (ws / "src").resolve()


def test_reject_traversal(ws):
    with pytest.raises(SecurityError) as exc:
        resolve_safe_path(ws, "../secret.py")
    assert exc.value.code == "PATH_TRAVERSAL"

    with pytest.raises(SecurityError) as exc:
        resolve_safe_path(ws, "src/../../tmp/x.py")
    assert exc.value.code == "PATH_TRAVERSAL"


def test_reject_absolute(ws):
    with pytest.raises(SecurityError) as exc:
        resolve_safe_path(ws, "/etc/passwd")
    assert exc.value.code == "ABSOLUTE_PATH"


def test_reject_drive_letter_and_unc(ws):
    if os.name == "nt":
        with pytest.raises(SecurityError) as exc:
            resolve_safe_path(ws, "C:/Windows/System32/x.dll")
        assert exc.value.code == "DRIVE_LETTER"
        with pytest.raises(SecurityError) as exc:
            resolve_safe_path(ws, "\\\\server\\share\\x.dll")
        assert exc.value.code == "UNC_PATH"


def test_reject_null_byte(ws):
    with pytest.raises(SecurityError) as exc:
        resolve_safe_path(ws, "src/calc.py\x00evil")
    assert exc.value.code == "NULL_BYTE"


def test_reject_symlink_component(tmp_path, ws):
    target = tmp_path / "outside.py"
    target.write_text("leaked\n", encoding="utf-8")
    (ws / "src" / "link.py").symlink_to(target)
    with pytest.raises(SecurityError) as exc:
        resolve_safe_path(ws, "src/link.py")
    assert exc.value.code == "SYMLINK_REJECTED"


def test_protected_tests_dir_is_not_patchable(ws):
    with pytest.raises(SecurityError) as exc:
        is_patchable(ws, "tests/test_calc.py", ["src/calc.py"])
    assert exc.value.code == "PROTECTED_FILE"


def test_allowlisted_src_file_is_patchable(ws):  # should not raise
    is_patchable(ws, "src/calc.py", ["src/calc.py"])


def test_non_python_file_rejected(ws):
    with pytest.raises(SecurityError) as exc:
        is_patchable(ws, "README.md", [])
    assert exc.value.code == "NOT_PYTHON_FILE"


def test_scrubbed_env_drops_secrets(ws):
    os.environ["REPOMEDIC_SECRET_TOKEN"] = "abc123"
    os.environ["API_KEY"] = "sk-test"
    try:
        env = scrubbed_env(ws)
        assert "REPOMEDIC_SECRET_TOKEN" not in env
        assert "API_KEY" not in env
        assert "PATH" in env
        assert env["PYTHONIOENCODING"] == "utf-8"
        assert env["PYTHONDONTWRITEBYTECODE"] == "1"
        assert "src" in env["PYTHONPATH"]
    finally:
        del os.environ["REPOMEDIC_SECRET_TOKEN"]
        del os.environ["API_KEY"]
