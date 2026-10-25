"""Patch engine: validate, diff, apply, rollback search/replace patches."""

import ast
import difflib
import hashlib
import os
import tempfile
from pathlib import Path
from typing import Optional

from app.config import BACKUPS_DIR, MAX_CHANGED_LINES, MAX_SNIPPET_CHARS, WORKSPACES_DIR
from app.core.security import is_patchable, resolve_safe_path, scrubbed_env
from app.schemas.patch import PatchApplyResult, PatchValidationResult, RepairProposal


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _read_raw_text_safe(path: Path) -> Optional[str]:
    """Read UTF-8 text preserving exact CRLF vs LF line endings."""
    try:
        raw = path.read_bytes()
        return raw.decode("utf-8")
    except (UnicodeDecodeError, OSError):
        return None


def _resolve_session_workspace(session_id: str, target_file: str, workspace_root: Optional[str | Path] = None) -> Path:
    if workspace_root is not None:
        return Path(workspace_root)
    base = WORKSPACES_DIR / session_id
    if (base / target_file).exists():
        return base
    if base.is_dir():
        subdirs = [d for d in base.iterdir() if d.is_dir()]
        if len(subdirs) == 1:
            return subdirs[0]
        for sub in subdirs:
            if (sub / target_file).exists():
                return sub
    return base


def _replace_normalized_lines(content: str, old_snippet: str, new_snippet: str) -> tuple[int, Optional[str], Optional[int]]:
    """Fallback matcher normalizing CRLF/LF and trailing whitespace per line.

    Returns (match_count, patched_content_or_None, start_line_or_None).
    """
    content_lines = content.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    old_lines = old_snippet.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    # Drop trailing empty line on snippet if snippet ended with newline
    if len(old_lines) > 1 and old_lines[-1] == "":
        old_lines = old_lines[:-1]
    n = len(old_lines)
    if n == 0 or n > len(content_lines):
        return (0, None, None)

    starts: list[int] = []
    for i in range(len(content_lines) - n + 1):
        if all(content_lines[i + j].rstrip() == old_lines[j].rstrip() for j in range(n)):
            starts.append(i)

    if len(starts) != 1:
        return (len(starts), None, None)

    start_line = starts[0]
    new_lines = new_snippet.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if len(new_lines) > 1 and new_lines[-1] == "" and not old_snippet.endswith("\n"):
        new_lines = new_lines[:-1]

    patched_lines = content_lines[:start_line] + new_lines + content_lines[start_line + n :]
    ending = "\r\n" if "\r\n" in content else "\n"
    patched = ending.join(patched_lines)
    return (1, patched, start_line)


def validate_patch(
    workspace_root: str | Path,
    target_file: str,
    proposal: RepairProposal,
    target_files: list[str],
) -> PatchValidationResult:
    """Validate a proposed patch end-to-end. Returns reason codes on failure."""
    result = PatchValidationResult()

    # 1. target_file allowlist + protection (also resolves path safely).
    try:
        is_patchable(workspace_root, target_file, target_files)
    except Exception as exc:  # noqa: BLE001
        code = getattr(exc, "code", "TARGET_NOT_ALLOWED")
        result.codes.append(code)
        return result

    resolved = resolve_safe_path(workspace_root, target_file)

    # 2. file exists and is UTF-8 text.
    if not resolved.exists():
        result.codes.append("FILE_NOT_FOUND")
        return result
    content = _read_raw_text_safe(resolved)
    if content is None:
        result.codes.append("NOT_UTF8")
        return result

    old_snippet = proposal.old_snippet
    new_snippet = proposal.new_snippet

    # Size limits.
    if len(old_snippet) > MAX_SNIPPET_CHARS or len(new_snippet) > MAX_SNIPPET_CHARS:
        result.codes.append("SIZE_EXCEEDED")
        return result

    # 3. new_snippet != old_snippet (defense in depth even if schema bypassed).
    if new_snippet == old_snippet:
        result.codes.append("NOOP_PATCH")
        return result

    # 4. old_snippet appears uniquely (exact substring first, then one CRLF/trailing-ws fallback).
    exact_count = content.count(old_snippet)
    normalized = False
    patched: Optional[str] = None
    found_line = 0

    if exact_count == 1:
        idx = content.find(old_snippet)
        found_line = content.count("\n", 0, idx)
        patched = content[:idx] + new_snippet + content[idx + len(old_snippet) :]
    elif exact_count > 1:
        result.codes.append("SNIPPET_AMBIGUOUS")
        return result
    else:
        norm_count, norm_patched, norm_line = _replace_normalized_lines(content, old_snippet, new_snippet)
        if norm_count == 0:
            result.codes.append("SNIPPET_NOT_FOUND")
            return result
        if norm_count > 1:
            result.codes.append("SNIPPET_AMBIGUOUS")
            return result
        normalized = True
        patched = norm_patched
        found_line = norm_line or 0

    assert patched is not None
    if patched == content:
        result.codes.append("NOOP_PATCH")
        return result

    # 5. Patched file must parse as valid Python.
    try:
        ast.parse(patched)
    except SyntaxError:
        result.codes.append("SYNTAX_INVALID")
        return result

    # Optional: ruff syntax-level check (E9). Non-blocking if ruff missing.
    try:
        import subprocess  # noqa: PLC0415

        proc = subprocess.run(
            ["ruff", "check", "--select", "E9", "--isolated", "-"],
            input=patched,
            text=True,
            capture_output=True,
            timeout=15,
            env=scrubbed_env(workspace_root),
        )
        if proc.returncode == 1 and proc.stdout.strip():
            result.codes.append("SYNTAX_INVALID")
            return result
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass

    before_lf = content.replace("\r\n", "\n")
    after_lf = patched.replace("\r\n", "\n")
    changed_lines = sum(1 for a, b in zip(before_lf.splitlines(), after_lf.splitlines()) if a != b) + abs(
        len(before_lf.splitlines()) - len(after_lf.splitlines())
    )
    if changed_lines > MAX_CHANGED_LINES:
        result.codes.append("SIZE_EXCEEDED")
        return result

    diff = generate_diff(before_lf, after_lf, target_file)

    result.ok = True
    result.diff = diff
    result.before = content
    result.after = patched
    result.snippet_normalized = normalized
    result.old_snippet_found_at = found_line
    return result


def generate_diff(before: str, after: str, target_file: str) -> str:
    return "\n".join(
        difflib.unified_diff(
            before.splitlines(),
            after.splitlines(),
            fromfile=f"a/{target_file}",
            tofile=f"b/{target_file}",
            lineterm="",
        )
    )


def apply_patch(
    session_id: str,
    attempt_n: int,
    target_file: str,
    proposal: RepairProposal,
    validation: PatchValidationResult,
    workspace_root: Optional[str | Path] = None,
) -> PatchApplyResult:
    """Back up the original file, then atomically write the patched content."""
    ws = _resolve_session_workspace(session_id, target_file, workspace_root)
    resolved = resolve_safe_path(ws, target_file)
    resolved.parent.mkdir(parents=True, exist_ok=True)

    before = validation.before if validation.before else (_read_raw_text_safe(resolved) or "")
    after = validation.after

    sha_before = _sha(before)
    sha_after = _sha(after)

    backup_dir = BACKUPS_DIR / session_id / f"attempt_{attempt_n}"
    backup_file = backup_dir / target_file
    backup_file.parent.mkdir(parents=True, exist_ok=True)
    backup_file.write_bytes(before.encode("utf-8"))

    # Atomic write: temp file in same directory, then os.replace.
    fd, tmp_path = tempfile.mkstemp(dir=str(resolved.parent), prefix=".repomedic-tmp-", suffix=".py")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(after.encode("utf-8"))
        os.replace(tmp_path, resolved)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

    return PatchApplyResult(
        ok=True,
        backup_path=str(backup_file),
        sha_before=sha_before,
        sha_after=sha_after,
        target_file=target_file,
    )


def rollback_patch(
    session_id: str,
    attempt_n: int,
    target_file: str,
    workspace_root: Optional[str | Path] = None,
) -> str:
    """Restore the pre-patch file from backup. Returns the restored sha-256."""
    ws = _resolve_session_workspace(session_id, target_file, workspace_root)
    resolved = resolve_safe_path(ws, target_file)
    backup_file = BACKUPS_DIR / session_id / f"attempt_{attempt_n}" / target_file
    if not backup_file.exists():
        raise FileNotFoundError(f"No backup found for {target_file} attempt {attempt_n}")
    raw = backup_file.read_bytes()
    content = raw.decode("utf-8")
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_bytes(raw)
    return _sha(content)
