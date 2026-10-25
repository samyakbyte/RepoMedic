"""Security helpers: safe path resolution, patch allowlist, scrubbed subprocess env."""

import os
from pathlib import Path
from typing import Optional

from app.config import PROTECTED_NAMES, PROTECTED_SUFFIXES
from app.schemas.common import ApiError


class SecurityError(Exception):
    def __init__(self, code: str, message: str, hint: str):
        self.code = code
        self.message = message
        self.hint = hint
        super().__init__(message)


def is_windows() -> bool:
    return os.name == "nt"


def resolve_safe_path(workspace_root: str | Path, relative_path: Optional[str]) -> Path:
    """Resolve a user/model-supplied relative path inside a workspace root.

    Rejects: None/empty, absolute paths, ".." traversal, drive letters,
    UNC paths, null bytes, symlinked components, and anything resolving
    outside the workspace root. Case-insensitive compare on Windows.
    """
    if relative_path is None or relative_path == "":
        raise SecurityError("EMPTY_PATH", "No file path was provided.", "Provide a relative path such as src/calc.py")

    if "\x00" in relative_path:
        raise SecurityError("NULL_BYTE", "Null byte in file path.", "Remove null bytes from the path")

    p = Path(relative_path.replace("/", os.sep) if is_windows() else relative_path)

    if p.is_absolute():
        raise SecurityError("ABSOLUTE_PATH", f"Absolute paths are not allowed: {relative_path}", "Use a relative path under the workspace, e.g. src/calc.py")

    parts = p.parts
    for part in parts:
        if part == "..":
            raise SecurityError(
                "PATH_TRAVERSAL",
                f"Path traversal is not allowed: {relative_path}",
                "Use a relative path without '..', e.g. src/calc.py",
            )
        if is_windows() and len(part) >= 2 and part[1] == ":":
            raise SecurityError("DRIVE_LETTER", f"Drive letters are not allowed: {relative_path}", "Use a relative path under the workspace")
        if part.startswith("\\\\"):
            raise SecurityError("UNC_PATH", f"UNC paths are not allowed: {relative_path}", "Use a relative path under the workspace")

    root = Path(workspace_root)
    candidate = (root / relative_path)

    # Reject if any component of the path (as it exists on disk) is a symlink,
    # walking from the workspace root down.
    walker = root
    for part in parts:
        walker = walker / part
        try:
            if walker.is_symlink():
                raise SecurityError(
                    "SYMLINK_REJECTED",
                    f"Symlinks are not allowed in workspace paths: {relative_path}",
                    "Use a regular file or directory, not a symlink",
                )
        except OSError:
            # Component does not exist yet; that is fine for new files.
            pass

    try:
        resolved = candidate.resolve(strict=False)
    except OSError as exc:
        raise SecurityError("PATH_RESOLVE_FAILED", f"Could not resolve path: {exc}", "Check the path and try again")

    root_resolved = root.resolve(strict=False)

    try:
        resolved.relative_to(root_resolved)
    except ValueError:
        raise SecurityError(
            "OUTSIDE_WORKSPACE",
            f"Path resolves outside the workspace: {relative_path}",
            "Keep the file inside the workspace, e.g. src/calc.py",
        )

    return resolved


def is_patchable(workspace_root: str | Path, relative_path: str, target_files: list[str]) -> None:
    """Raise SecurityError if the file is not in the patch allowlist.

    Only .py files under src/ or listed in target_files are patchable.
    Protected files (tests/, conftest.py, pytest.ini, project.json, setup.py,
    pyproject.toml, tox.ini, requirements*.txt) are never patchable.
    """
    rel = relative_path.replace("\\", "/")
    resolve_safe_path(workspace_root, relative_path)  # raises on traversal/symlink/etc.

    if not rel.endswith(".py"):
        raise SecurityError("NOT_PYTHON_FILE", f"Not a Python file: {rel}", "Only .py source files can be patched")

    name = Path(rel).name
    if name in PROTECTED_NAMES:
        raise SecurityError(
            "PROTECTED_FILE",
            f"Protected file, cannot be patched: {rel}",
            "RepoMedic only fixes source code, never tests or project configuration",
        )
    if rel.startswith("tests" + "/") or rel == "tests":
        raise SecurityError(
            "PROTECTED_FILE",
            f"Protected file, cannot be patched: {rel}",
            "RepoMedic only fixes source code, never tests or project configuration",
        )
    if any(rel.endswith(sfx) for sfx in PROTECTED_SUFFIXES):
        raise SecurityError(
            "PROTECTED_FILE",
            f"Protected file, cannot be patched: {rel}",
            "Dependency files are not patchable by the model",
        )

    under_src = rel.startswith("src" + "/") or rel == "src"
    in_targets = rel in target_files
    if not (under_src or in_targets):
        raise SecurityError(
            "TARGET_NOT_ALLOWED",
            f"File is not in the patch allowlist: {rel}",
            "Only .py files under src/ (or listed target_files) can be patched",
        )


def scrubbed_env(workspace_root: str | Path) -> dict[str, str]:
    """Return a minimal environment for subprocess execution.

    Only PATH, SYSTEMROOT, TEMP, TMP, PYTHONIOENCODING, PYTHONDONTWRITEBYTECODE
    and PYTHONPATH are passed; all tokens/API keys are dropped.
    """
    base_ws = str(workspace_root)
    env: dict[str, str] = {}
    for key in ("PATH", "SYSTEMROOT", "TEMP", "TMP"):
        val = os.environ.get(key)
        if val:
            env[key] = val
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = str(Path(base_ws) / "src")
    return env
