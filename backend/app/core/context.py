"""Context builder: assembles a bounded prompt for the local repair model.

Includes: failing test + assertion message, short traceback, failing test
source, source files referenced in the traceback (line numbers for humans),
related function bodies. Never includes reference solutions or other sessions.
"""

from typing import Optional

from app.config import REPOMEDIC_MAX_CONTEXT_CHARS
from app.core.diagnostics import DiagnosticsResult, Failure
from app.core.security import resolve_safe_path
from app.schemas.diagnostic import DiagnosticsResult as _Diag  # noqa: F401  (alias for clarity)
from app.schemas.patch import RepairProposal
from app.schemas.session import VerificationResult


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
        previous_verification: Optional[VerificationResult] = None,
    ) -> str:
        sections: list[str] = []

        sections.append(self._section("REPOMEDIC repair context", f"project: {project_name}\n{project_description}\n"))
        sections.append(self._section("TASK", "Produce a minimal search/replace patch that makes the failing tests pass without breaking any previously passing test. Change source code only, never tests."))

        sections.append(self._section("FAILING TEST", f"test_id: {failing_test_id}"))
        if diagnostics.failures:
            for failure in diagnostics.failures[:3]:
                sections.append(self._section("FAILURE", f"message: {failure.message}"))
                if failure.traceback:
                    sections.append(self._section("TRACEBACK (short)", self._short_traceback(failure.traceback)))

        # Sources referenced in tracebacks
        referenced_files: list[str] = []
        for failure in diagnostics.failures:
            if failure.file:
                referenced_files.append(failure.file)

        # Failing test source first
        test_files = [f for f in referenced_files if f.startswith("tests/")]
        for tf in test_files:
            content = self._read_file(workspace_root, tf)
            if content is not None:
                sections.append(self._section(f"TEST SOURCE ({tf})", self._numbered(content)))

        # Then source files (non-test)
        src_files = [f for f in referenced_files if not f.startswith("tests/")]
        seen: set[str] = set()
        for sf in src_files:
            if sf in seen:
                continue
            seen.add(sf)
            content = self._read_file(workspace_root, sf)
            if content is not None:
                sections.append(self._section(f"SOURCE FILE (line numbers for humans only) {sf}", self._numbered(content)))

        # Related function bodies: functions mentioned in failure messages/tracebacks are
        # already covered by the source files above; keep this section for the
        # smallest useful targeted context.

        body = "\n".join(sections)

        if previous_attempt is not None or previous_verification is not None:
            retry = ["", "--- PREVIOUS ATTEMPT (did not lead to a verified repair) ---"]
            if previous_attempt is not None:
                retry.append(f"target_file: {previous_attempt.get('target_file', '')}")
                retry.append(f"old_snippet: {previous_attempt.get('old_snippet', '')}")
                retry.append(f"new_snippet: {previous_attempt.get('new_snippet', '')}")
                retry.append(f"explanation: {previous_attempt.get('explanation', '')}")
            if previous_verification is not None:
                retry.append(f"verdict: {previous_verification.get('verdict', '')}")
                retry.append(f"reason: {previous_verification.get('reason', '')}")
                retry.append(f"regressions: {previous_verification.get('regressions', [])}")
                retry.append(f"still failing: {previous_verification.get('originally_failing_now_passing', [])}")
                if previous_verification.get("raw_output"):
                    retry.append("verification output (trimmed):")
                    retry.append(self._trim(previous_verification["raw_output"], 1500))
            body += "\n" + "\n".join(retry)

        return self._truncate(body)

    # ---- helpers ---------------------------------------------------------

    @staticmethod
    def _section(title: str, content: str) -> str:
        return f"### {title}\n{content.strip()}\n"

    @staticmethod
    def _read_file(workspace_root: str, relative_path: str) -> Optional[str]:
        try:
            resolved = resolve_safe_path(workspace_root, relative_path)
            return resolved.read_text(encoding="utf-8")
        except Exception:
            return None

    @staticmethod
    def _numbered(content: str) -> str:
        lines = content.splitlines()
        out = []
        for i, line in enumerate(lines, start=1):
            out.append(f"{i:4d}: {line}")
        return "\n".join(out)

    @staticmethod
    def _short_traceback(traceback: str) -> str:
        lines = [l for l in traceback.splitlines() if l.strip()]
        # Keep the last 8 lines (usually the assertion line), drop verbose library frames.
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
