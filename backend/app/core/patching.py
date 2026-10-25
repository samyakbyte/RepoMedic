"""Patch engine: validate, diff, apply, rollback search/replace patches."""

import ast
import difflib
import hashlib
import os
import shutil
import tempfile
from pathlib import Path
from typing import Optional, Union

from app.config import BACKUPS_DIR, MAX_CHANGED_LINES, MAX_SNIPPET_CHARS, WORKSPACES_DIR
from app.core.security import is_patchable, resolve_safe_path, scrubbed_env
from app.schemas.patch import PatchApplyResult, PatchValidationResult, RepairProposal

_MATCH_AMBIGUOUS = "ambiguous"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _read_text_safe(path: Path) -> Optional[str]:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None
    except OSError:
        return None


def _find_unique_match(content: str, old_snippet: str) -> Union[None, str, tuple]:
    """Locate old_snippet in content line by line.

    Exact match is preferred; if none, one normalization fallback for line
    endings (CRLF vs LF) and trailing whitespace is allowed.

    Returns:
        None                              -> snippet not found
        _MATCH_AMBIGUOUS                  -> more than one match
        (start_line, line_count, normalized) -> unique match
    """
    content_lines = content.splitlines()
    old_lines = old_snippet.splitlines()
    n = len(old_lines)
    if n == 0 or n > len(content_lines):
        return None

    chosen = None
    for normalized in (False, True):
        starts = []
        for i in range(len(content_lines) - n + 1):
            ok = True
            for j in range(n):
                a, b = content_lines[i + j], old_lines[j]
                if normalized:
                    if a.rstrip() != b.rstrip():
                        ok = False
                        break
                else:
                    if a != b:
                        ok = False
                        break
            if ok:
                starts.append(i)
        if starts:
            chosen = (normalized, starts)
            break  # exact match preferred over normalized fallback

    if chosen is None:
        return None
    normalized, starts = chosen
    if len(starts) > 1:
        return _MATCH_AMBIGUOUS
    return (starts[0], n, normalized)


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
    content = _read_text_safe(resolved)
    if content is None:
        result.codes.append("NOT_UTF8")
        return result

    old_snippet = proposal.old_snippet
    new_snippet = proposal.new_snippet

    # Size limits.
    if len(old_snippet) > MAX_SNIPPET_CHARS or len(new_snippet) > MAX_SNIPPET_CHARS:
        result.codes.append("SIZE_EXCEEDED")
        return result

    # 3. old_snippet appears exactly once (with one line-ending/trailing-ws fallback).
    match = _find_unique_match(content, old_snippet)
    if match is None:
        result.codes.append("SNIPPET_NOT_FOUND")
        return result
    if match == _MATCH_AMBIGUOUS:
        result.codes.append("SNIPPET_AMBIGUOUS")
        return result
    start_line, line_count, normalized = match

    # 4. new_snippet != old_snippet.
    if new_snippet == old_snippet:
        result.codes.append("NOOP_PATCH")
        return result

    # 5. Build the patched content and check it parses as valid Python.
    content_lines = content.splitlines()
    new_lines = new_snippet.splitlines()
    patched_lines = content_lines[:start_line] + new_lines + content_lines[start_line + line_count:]
    ending = "\r\n" if "\r\n" in content else "\n"
    trailing_newline = "\n" if content.endswith("\n") else ""
    patched = ending.join(patched_lines) + trailing_newline

    try:
        ast.parse(patched)
    except SyntaxError:
        result.codes.append("SYNTAX_INVALID")
        return result

    # Optional: ruff syntax-level check (E9, F). Non-blocking if ruff missing.
    try:
        import subprocess  # noqa: PLC0415

        proc = subprocess.run(
            ["ruff", "check", "--select", "E9,F", "--isolated", "/dev/stdin"],
            input=patched,
            text=True,
            capture_output=True,
            timeout=15,
            env=scrubbed_env(workspace_root),
        )
        if proc.returncode not in (0, 1):
            if proc.stdout.strip():
                result.codes.append("SYNTAX_INVALID")
                return result
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass  # ruff not installed or timed out: proceed with ast.parse result

    changed_lines = sum(1 for a, b in zip(content.splitlines(), patched.splitlines()) if a != b) + abs(
        len(content.splitlines()) - len(patched.splitlines())
    )
    if changed_lines > MAX_CHANGED_LINES:
        result.codes.append("SIZE_EXCEEDED")
        return result

    # Build unified diff + before/after for the viewer.
    diff = "\n".join(
        difflib.unified_diff(
            content.splitlines(keepends=True),
            patched.splitlines(keepends=True),
            fromfile=f"a/{target_file}",
            tofile=f"b/{target_file}",
            lineterm="",
        )
    )

    result.ok = True
    result.diff = diff
    result.before = content
    result.after = patched
    result.snippet_normalized = normalized
    result.old_snippet_found_at = start_line
    return result


def generate_diff(before: str, after: str, target_file: str) -> str:
    return "\n".join(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile=f"a/{target_file}",
            tofile=f"b/{target_file}",
            lineterm="",
        )
    )


def apply_patch(session_id: str, attempt_n: int, target_file: str, proposal: RepairProposal, validation: PatchValidationResult) -> PatchApplyResult:
    """Back up the original file, then atomically write the patched content."""
    ws = WORKSPACES_DIR / session_id
    resolved = resolve_safe_path(ws, target_file)

    before = validation.before or _read_text_safe(resolved) or ""
    after = validation.after

    sha_before = _sha(before)
    sha_after = _sha(after)

    backup_dir = BACKUPS_DIR / session_id / f"attempt_{attempt_n}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    # Preserve subdirectory structure inside backups.
    backup_file = backup_dir / target_file
    backup_file.parent.mkdir(parents=True, exist_ok=True)
    backup_file.write_text(before, encoding="utf-8")

    # Atomic write: temp file in same directory, then os.replace.
    fd, tmp_path = tempfile.mkstemp(dir=str(resolved.parent), prefix=".repomedic-tmp-", suffix=".py")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(after)
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


def rollback_patch(session_id: str, attempt_n: int, target_file: str) -> str:
    """Restore the pre-patch file from backup. Returns the restored sha-256."""
    ws = WORKSPACES_DIR / session_id
    resolved = resolve_safe_path(ws, target_file)
    backup_file = BACKUPS_DIR / session_id / f"attempt_{attempt_n}" / target_file
    if not backup_file.exists():
        raise FileNotFoundError(f"No backup found for {target_file} attempt {attempt_n}")
    content = backup_file.read_text(encoding="utf-8")
    resolved.write_text(content, encoding="utf-8")
    return _sha(content)
