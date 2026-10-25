"""Session endpoints: create, diagnose, repair, patch, approve, reject, rollback, reset, report."""

from typing import Optional

from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel, Field

from app.app_core import context_builder, llm_client, store, verifier, workspace_manager
from app.config import MAX_ATTEMPTS, PYTEST_TIMEOUT_S, REPORTS_DIR, WORKSPACES_DIR
from app.core.diagnostics import run_pytest
from app.core.llm import OllamaError
from app.core.patching import apply_patch, rollback_patch, validate_patch
from app.core.reports import write_report
from app.core.security import resolve_safe_path
from app.schemas.common import ApiError, SessionState, new_session_id
from app.schemas.session import AttemptRecord, LLMMetrics

router = APIRouter()


class CreateSessionBody(BaseModel):
    project_id: str = Field(..., description="Demo project id, e.g. calculator-bug")


class RejectBody(BaseModel):
    reason: Optional[str] = Field(None, description="Optional human reason for rejecting the patch")


def _workspace_for(session) -> str:
    return str(WORKSPACES_DIR / session.id / session.project_id)


def _previous_attempt_info(session):
    if not session.attempts:
        return None, None
    last = session.attempts[-1]
    prev_patch = last.patch.model_dump() if last.patch else None
    prev_verification = last.verification.model_dump() if last.verification else None
    return prev_patch, prev_verification


# ---- background tasks (sync -> FastAPI runs them in threadpool) -----------

def _run_diagnose_sync(session_id: str) -> None:
    try:
        session = store.get(session_id)
        if session.state != SessionState.DIAGNOSING:
            return
        project = workspace_manager.get_project(session.project_id)
        ws = _workspace_for(session)
        diag = run_pytest(ws, project.test_command, timeout_s=PYTEST_TIMEOUT_S)
        store.set_diagnostics(session_id, diag)
        if diag.error_type or diag.failed > 0 or diag.errors > 0:
            store.transition(
                session_id,
                SessionState.FAILURE_DETECTED,
                f"{diag.failed} failed, {diag.errors} errors ({diag.error_type or 'tests'})",
            )
        else:
            store.transition(session_id, SessionState.IDLE, "All tests pass, nothing to repair")
    except Exception as exc:  # noqa: BLE001
        try:
            store.transition(session_id, SessionState.ERROR, f"diagnostics crashed: {exc}")
        except Exception:
            pass


async def _run_diagnose(session_id: str) -> None:
    _run_diagnose_sync(session_id)


def _run_repair_sync(session_id: str) -> None:
    try:
        session = store.get(session_id)
        if session.state != SessionState.GENERATING_REPAIR:
            return
        project = workspace_manager.get_project(session.project_id)
        ws = _workspace_for(session)
        diag = session.diagnostics_before
        attempt_n = session.attempt + 1
        prev_patch, prev_verification = _previous_attempt_info(session)

        context = context_builder.build(
            ws,
            diag,
            project.failing_test,
            project.name,
            project.description,
            previous_attempt=prev_patch,
            previous_verification=prev_verification,
            target_files=project.target_files,
        )

        try:
            llm_result = llm_client.generate_repair(context)
        except OllamaError as exc:
            store.transition(session_id, SessionState.ERROR, f"{exc.code}: {exc.message} ({exc.hint})")
            return

        proposal = llm_result.proposal
        validation = validate_patch(ws, proposal.target_file, proposal, project.target_files)

        attempt = AttemptRecord(
            n=attempt_n,
            patch=proposal,
            validation=validation,
            llm=LLMMetrics(
                model=llm_result.model,
                duration_s=llm_result.duration_s,
                prompt_eval_count=llm_result.prompt_eval_count,
                eval_count=llm_result.eval_count,
                eval_duration_ns=llm_result.eval_duration_ns,
                total_duration_ns=llm_result.total_duration_ns,
                load_duration_ns=llm_result.load_duration_ns,
                tokens_per_second=llm_result.tokens_per_second,
            ),
        )
        store.add_attempt(session_id, attempt)

        if not validation.ok:
            store.transition(
                session_id,
                SessionState.ERROR,
                "Patch validation failed: " + ", ".join(validation.codes),
            )
            return

        store.transition(session_id, SessionState.PATCH_READY, f"Attempt {attempt_n}: patch validated ({proposal.target_file})")
        store.transition(session_id, SessionState.AWAITING_APPROVAL, "Waiting for human approval")
    except Exception as exc:  # noqa: BLE001
        try:
            store.transition(session_id, SessionState.ERROR, f"repair generation crashed: {exc}")
        except Exception:
            pass


async def _run_repair(session_id: str) -> None:
    _run_repair_sync(session_id)


def _run_apply_verify_sync(session_id: str) -> None:
    try:
        session = store.get(session_id)
        if session.state != SessionState.APPLYING_PATCH:
            return
        project = workspace_manager.get_project(session.project_id)
        ws = _workspace_for(session)
        attempt = session.attempts[-1]

        apply_patch(
            session_id,
            attempt.n,
            attempt.patch.target_file,
            attempt.patch,
            attempt.validation,
            workspace_root=ws,
        )

        store.transition(session_id, SessionState.VERIFYING, f"Rerunning pytest to verify attempt {attempt.n}")

        session = store.get(session_id)
        previously_failing = [f.test_id for f in (session.diagnostics_before.failures if session.diagnostics_before else [])]
        previously_passing = list(session.diagnostics_before.passing_tests if session.diagnostics_before else [])
        verification = verifier.verify(ws, project.test_command, previously_failing, previously_passing)

        session = store.get(session_id)
        session.attempts[-1].verification = verification
        session.attempts[-1].approved = True
        session.verdict = verification.verdict
        store.save(session)

        if verification.verdict == "REPAIR_VERIFIED":
            store.transition(session_id, SessionState.REPAIR_VERIFIED, "Repair verified: all tests pass, zero regressions")
        else:
            store.transition(
                session_id,
                SessionState.REPAIR_FAILED,
                verification.reason or "verification failed",
            )
        write_report(store.get(session_id))
    except Exception as exc:  # noqa: BLE001
        try:
            store.transition(session_id, SessionState.ERROR, f"apply/verify crashed: {exc}")
        except Exception:
            pass


async def _run_apply_verify(session_id: str) -> None:
    _run_apply_verify_sync(session_id)


# ---- routes ---------------------------------------------------------------

@router.post("", status_code=201)
def create_session(body: CreateSessionBody):
    project = workspace_manager.get_project(body.project_id)
    if project is None:
        raise ApiError("UNKNOWN_PROJECT", f"Unknown project: {body.project_id}", "Call GET /api/projects for the list")
    session_id = new_session_id()
    workspace_manager.create_workspace(session_id, body.project_id)
    session = store.create(session_id, body.project_id)
    return store.summary(session)


@router.get("")
def list_sessions():
    return store.list_sessions()


@router.get("/{session_id}")
def get_session(session_id: str):
    return store.get(session_id)


@router.get("/{session_id}/files")
def get_session_files(session_id: str):
    """Return workspace source and test files (read-only view for UI inspection)."""
    session = store.get(session_id)
    project = workspace_manager.get_project(session.project_id)
    ws = _workspace_for(session)
    files: dict[str, str] = {}
    candidates = list(project.target_files)
    if "::" in project.failing_test:
        candidates.append(project.failing_test.split("::", 1)[0])
    for rel in candidates:
        try:
            p = resolve_safe_path(ws, rel)
            if p.is_file():
                files[rel] = p.read_text(encoding="utf-8")
        except Exception:
            continue
    return {"session_id": session_id, "project_id": session.project_id, "files": files}


@router.post("/{session_id}/diagnose", status_code=202)
def diagnose(session_id: str, background_tasks: BackgroundTasks):
    store.get(session_id)  # 404 if missing
    store.transition(session_id, SessionState.DIAGNOSING, "Running pytest diagnostics")
    background_tasks.add_task(_run_diagnose_sync, session_id)
    return {"session_id": session_id, "state": SessionState.DIAGNOSING}


@router.post("/{session_id}/repair", status_code=202)
def repair(session_id: str, background_tasks: BackgroundTasks):
    session = store.get(session_id)
    if session.attempt >= MAX_ATTEMPTS and session.state != SessionState.IDLE:
        raise ApiError(
            "ATTEMPTS_EXHAUSTED",
            f"Maximum {MAX_ATTEMPTS} repair attempts reached for this session",
            "Reset the session to start over",
            state=session.state.value,
            status_code=409,
        )
    store.transition(session_id, SessionState.GENERATING_REPAIR, f"Starting attempt {session.attempt + 1}")
    background_tasks.add_task(_run_repair_sync, session_id)
    return {"session_id": session_id, "state": SessionState.GENERATING_REPAIR, "attempt": session.attempt + 1}


@router.get("/{session_id}/patch")
def get_patch(session_id: str):
    session = store.get(session_id)
    if not session.attempts:
        raise ApiError("NO_PATCH", "No patch exists for this session", "Generate a repair first", state=session.state.value, status_code=404)
    attempt = session.attempts[-1]
    return {
        "session_id": session_id,
        "state": session.state,
        "attempt": attempt.n,
        "patch": attempt.patch,
        "validation": attempt.validation,
        "approved": attempt.approved,
        "verification": attempt.verification,
        "llm": attempt.llm,
    }


@router.post("/{session_id}/approve", status_code=202)
def approve(session_id: str, background_tasks: BackgroundTasks):
    session = store.get(session_id)
    if session.state != SessionState.AWAITING_APPROVAL:
        raise ApiError(
            "STATE_CONFLICT",
            f"Cannot approve in state {session.state}",
            "Approval is only possible when state is AWAITING_APPROVAL",
            state=session.state.value,
            status_code=409,
        )
    attempt = session.attempts[-1]
    if not attempt.validation.ok:
        raise ApiError("PATCH_INVALID", "Current patch did not pass validation", state=session.state.value, status_code=409)
    store.transition(session_id, SessionState.APPLYING_PATCH, "User approved patch; applying to workspace")
    background_tasks.add_task(_run_apply_verify_sync, session_id)
    return {"session_id": session_id, "state": SessionState.APPLYING_PATCH, "attempt": attempt.n}


@router.post("/{session_id}/reject")
def reject(session_id: str, body: RejectBody = RejectBody()):
    session = store.get(session_id)
    if session.state != SessionState.AWAITING_APPROVAL:
        raise ApiError(
            "STATE_CONFLICT",
            f"Cannot reject in state {session.state}",
            "Reject is only possible when state is AWAITING_APPROVAL",
            state=session.state.value,
            status_code=409,
        )
    attempt = session.attempts[-1]
    attempt.rejected_reason = body.reason or "User rejected the patch"
    store.save(session)
    store.transition(session_id, SessionState.FAILURE_DETECTED, "Patch rejected by user; may regenerate")
    return {"session_id": session_id, "state": SessionState.FAILURE_DETECTED, "attempt": attempt.n}


@router.post("/{session_id}/rollback")
def rollback(session_id: str):
    session = store.get(session_id)
    if not session.attempts:
        raise ApiError("NO_PATCH", "No patch to roll back", "Apply a patch first", state=session.state.value, status_code=409)
    attempt = session.attempts[-1]
    ws = _workspace_for(session)
    try:
        restored_sha = rollback_patch(session.id, attempt.n, attempt.patch.target_file, workspace_root=ws)
    except FileNotFoundError as exc:
        raise ApiError("NO_BACKUP", f"No backup found for attempt {attempt.n}", str(exc), state=session.state.value, status_code=409)
    store.set_verdict(session_id, None)
    next_state = SessionState.FAILURE_DETECTED if attempt.n < MAX_ATTEMPTS else SessionState.IDLE
    store.transition(session_id, next_state, f"Rolled back attempt {attempt.n} (sha {restored_sha[:12]})")
    return {"session_id": session_id, "state": next_state, "restored_sha": restored_sha}


@router.post("/{session_id}/reset")
def reset(session_id: str):
    session = store.get(session_id)
    workspace_manager.cleanup(session.id)
    workspace_manager.create_workspace(session.id, session.project_id)
    new_session = store.create(session.id, session.project_id)
    return store.summary(new_session)


@router.get("/{session_id}/report")
def get_report(session_id: str, format: str = "json"):
    session = store.get(session_id)
    report_path = write_report(session)
    if format == "md":
        markdown = _markdown_report(session)
        return PlainTextResponse(markdown, media_type="text/markdown")
    return FileResponse(report_path, media_type="application/json", filename=f"{session_id}.json")


def _markdown_report(session) -> str:
    lines = [f"# RepoMedic Report: {session.id}", ""]
    lines.append(f"- **Project**: `{session.project_id}`")
    lines.append(f"- **State**: `{session.state.value}`")
    lines.append(f"- **Verdict**: `{session.verdict or '-'}`")
    lines.append(f"- **Attempts**: {session.attempt}/{session.max_attempts}")
    lines.append("")
    if session.diagnostics_before:
        d = session.diagnostics_before
        lines.append("## Initial Diagnostics")
        lines.append(f"- Passed: {d.passed}, Failed: {d.failed}, Errors: {d.errors}, Duration: {d.duration_s:.2f}s")
        for f in d.failures:
            lines.append(f"- FAIL `{f.test_id}`: {f.message}")
        lines.append("")
    if session.attempts:
        lines.append("## Repair Attempts")
        for att in session.attempts:
            lines.append(f"### Attempt {att.n} (`{att.patch.target_file}`)")
            lines.append(f"- **Root cause**: {att.patch.root_cause}")
            lines.append(f"- **Explanation**: {att.patch.explanation}")
            lines.append(f"- **Validation OK**: {att.validation.ok} ({', '.join(att.validation.codes) or 'clean'})")
            if att.validation.diff:
                lines.append("```diff")
                lines.append(att.validation.diff)
                lines.append("```")
            if att.verification:
                lines.append(
                    f"- **Verification**: `{att.verification.verdict}` "
                    f"({att.verification.passed} passed, {att.verification.failed} failed)"
                )
            lines.append("")
    lines.append("## Timeline")
    for entry in session.timeline:
        lines.append(f"- `{entry.at}` **{entry.state.value}**" + (f" — {entry.note}" if entry.note else ""))
    return "\n".join(lines)
