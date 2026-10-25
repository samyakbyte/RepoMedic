"""Context builder: assembles a bounded prompt for the local repair model.

Includes: failing test + assertion message, short traceback, failing test
source, source files in the workspace (line numbers for humans), and retry
feedback when applicable. Never includes reference solutions or other sessions.
"""

import os
from pathlib import Path
from typing import Optional

from app.config import REPOMEDIC_MAX_CONTEXT_CHARS
from app.core.diagnostics import DiagnosticsResult
from app.core.security import resolve_safe_path


class ContextBuilder:
    def __init__(self, max_chars: int = REPOMEDIC_MAX_CONTEXT_CHARS):
        self.max_chars = max_chars

    def build(
        self,
        workspace_root: str,
        diagnostics: DiagnosticsResult,
        failing_test_id: str,
        project_name: str,
        project_description: str,
        previous_attempt: Optional[dict] = None,
        previous_verification: Optional[dict] = None,
        target_files: Optional[list[str]] = None,
    ) -> str:
        sections: list[str] = []

        sections.append(
            self._section(
                "REPOMEDIC repair context",
                f"project: {project_name}\n{project_description}\n",
            )
        )
        sections.append(
            self._section(
                "TASK",
                "Produce a minimal search/replace patch that makes the failing tests pass "
                "without breaking any previously passing test. Change source code only (under src/), never tests.",
            )
        )

        sections.append(self._section("FAILING TEST", f"test_id: {failing_test_id}"))
        if diagnostics.failures:
            for failure in diagnostics.failures[:3]:
                sections.append(self._section("FAILURE", f"test: {failure.test_id}\nmessage: {failure.message}"))
                if failure.traceback:
                    sections.append(self._section("TRACEBACK (short)", self._short_traceback(failure.traceback)))

        referenced_files: list[str] = []
        for failure in diagnostics.failures:
            if failure.file:
                referenced_files.append(failure.file.replace("\\", "/"))
        if "::" in failing_test_id:
            tf_candidate = failing_test_id.split("::", 1)[0].replace("\\", "/")
            if tf_candidate not in referenced_files:
                referenced_files.append(tf_candidate)

        # Failing test source first
        seen_tests: set[str] = set()
        for tf in referenced_files:
            if not tf.startswith("tests/") or tf in seen_tests:
                continue
            seen_tests.add(tf)
            content = self._read_file(workspace_root, tf)
            if content is not None:
                sections.append(self._section(f"TEST SOURCE ({tf})", self._numbered(content)))

        # Candidate source files: explicit target_files + non-test referenced files + workspace src/**/*.py
        src_candidates: list[str] = []
        if target_files:
            src_candidates.extend(f.replace("\\", "/") for f in target_files)
        for rf in referenced_files:
            if not rf.startswith("tests/"):
                src_candidates.append(rf)
        src_candidates.extend(self._discover_src_files(workspace_root))

        seen_src: set[str] = set()
        for sf in src_candidates:
            if sf in seen_src:
                continue
            seen_src.add(sf)
            content = self._read_file(workspace_root, sf)
            if content is not None:
                sections.append(
                    self._section(
                        f"SOURCE FILE (target_file={sf}; line numbers are for reference only — do NOT include line numbers in old_snippet/new_snippet)",
                        self._numbered(content),
                    )
                )

        body = "\n".join(sections)

        if previous_attempt is not None or previous_verification is not None:
            retry = ["", "--- PREVIOUS ATTEMPT (did not lead to a verified repair) ---"]
            if previous_attempt is not None:
                retry.append(f"target_file: {previous_attempt.get('target_file', '')}")
                retry.append(f"old_snippet: {previous_attempt.get('old_snippet', '')}")
                retry.append(f"new_snippet: {previous_attempt.get('new_snippet', '')}")
                retry.append(f"explanation: {previous_attempt.get('explanation', '')}")
            if previous_verification is not None:
                vp = previous_verification if isinstance(previous_verification, dict) else previous_verification.model_dump()
                retry.append(f"verdict: {vp.get('verdict', '')}")
                retry.append(f"reason: {vp.get('reason', '')}")
                retry.append(f"regressions: {vp.get('regressions', [])}")
                retry.append(f"still failing: {vp.get('originally_failing_now_passing', [])}")
                if vp.get("raw_output"):
                    retry.append("verification output (trimmed):")
                    retry.append(self._trim(str(vp["raw_output"]), 1500))
            body += "\n" + "\n".join(retry)

        return self._truncate(body)

    # ---- helpers ---------------------------------------------------------

    @staticmethod
    def _discover_src_files(workspace_root: str) -> list[str]:
        root = Path(workspace_root)
        src_dir = root / "src"
        found: list[str] = []
        if not src_dir.is_dir() or src_dir.is_symlink():
            return found
        for dirpath, dirnames, filenames in os.walk(src_dir):
            dirnames[:] = sorted(d for d in dirnames if d not in ("__pycache__", ".pytest_cache"))
            for fname in sorted(filenames):
                if fname.endswith(".py") and fname != "__init__.py":
                    rel = os.path.relpath(Path(dirpath) / fname, root).replace("\\", "/")
                    found.append(rel)
        return found

    @staticmethod
    def _section(title: str, content: str) -> str:
        return f"### {title}\n{content.strip()}\n"

    @staticmethod
    def _read_file(workspace_root: str, relative_path: str) -> Optional[str]:
        try:
            resolved = resolve_safe_path(workspace_root, relative_path)
            if not resolved.is_file():
                return None
            return resolved.read_text(encoding="utf-8")
        except Exception:
            return None

    @staticmethod
    def _numbered(content: str) -> str:
        lines = content.splitlines()
        return "\n".join(f"{i:4d}: {line}" for i, line in enumerate(lines, start=1))

    @staticmethod
    def _short_traceback(traceback: str) -> str:
        lines = [line for line in traceback.splitlines() if line.strip()]
        return "\n".join(lines[-8:]) if lines else ""

    @staticmethod
    def _trim(text: str, limit: int) -> str:
        text = text.strip()
        if len(text) <= limit:
            return text
        return text[:limit] + "\n...[trimmed]..."

    def _truncate(self, body: str) -> str:
        if len(body) <= self.max_chars:
            return body
        cut = body[: self.max_chars]
        last_newline = cut.rfind("\n")
        if last_newline > self.max_chars * 0.8:
            cut = cut[:last_newline]
        return cut + "\n...[context truncated by RepoMedic]..."
