#!/usr/bin/env python3
"""RepoMedic repair CLI (Phase 2 acceptance).

Runs: diagnose -> generate -> validate -> print diff -> (human approval, or
--auto-approve for benchmarks) -> apply -> verify -> report.
No frontend, no hosted AI: the local Ollama model does the real work.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.app_core import context_builder, llm_client, store, verifier, workspace_manager
from app.config import MAX_ATTEMPTS, PYTEST_TIMEOUT_S
from app.core.diagnostics import run_pytest
from app.core.patching import apply_patch, validate_patch
from app.core.reports import write_report
from app.core.state_machine import SessionState
from app.schemas.common import new_session_id


def main() -> int:
    parser = argparse.ArgumentParser(description="RepoMedic repair CLI")
    parser.add_argument("--project", required=True, help="demo project id (e.g. calculator-bug)")
    parser.add_argument(
        "--auto-approve",
        action="store_true",
        help="approve patches without prompting (benchmark mode only)",
    )
    args = parser.parse_args()

    project = workspace_manager.get_project(args.project)
    if project is None:
        print(f"Unknown project: {args.project}")
        print("Run with one of: " + ", ".join(p.id for p in workspace_manager.list_projects()))
        return 2

    session_id = new_session_id()
    ws = workspace_manager.create_workspace(session_id, args.project)
    store.create(session_id, args.project)
    print(f"RepoMedic CLI — session {session_id}, project {args.project}")
    print(f"Workspace: {ws}")

    # 1. Diagnose
    print("\n[1/6] Diagnose: running", " ".join(project.test_command))
    store.transition(session_id, SessionState.DIAGNOSING, "Running pytest diagnostics")
    diag = run_pytest(ws, project.test_command, timeout_s=PYTEST_TIMEOUT_S)
    print(f"  {diag.passed} passed, {diag.failed} failed, {diag.errors} errors in {diag.duration_s:.2f}s")
    if diag.error_type:
        print(f"  error type: {diag.error_type}")
    for f in diag.failures[:5]:
        print(f"  FAIL {f.test_id}: {f.message}")
    if diag.failed == 0 and diag.errors == 0 and not diag.error_type:
        store.transition(session_id, SessionState.IDLE, "All tests pass")
        print("All tests pass. Nothing to repair.")
        return 0

    store.set_diagnostics(session_id, diag)
    store.transition(session_id, SessionState.FAILURE_DETECTED, f"{diag.failed} failing test(s)")

    previously_failing = [f.test_id for f in diag.failures]
    verified = False
    attempt = 0

    while attempt < MAX_ATTEMPTS and not verified:
        attempt += 1
        print(f"\n[2/6] Attempt {attempt} of {MAX_ATTEMPTS}: generate repair")
        store.transition(session_id, SessionState.GENERATING_REPAIR, f"Attempt {attempt}")
        session = store.get(session_id)
        prev = session.attempts[-1] if session.attempts else None
        context = context_builder.build(
            str(ws),
            diag,
            project.failing_test,
            project.name,
            project.description,
            previous_attempt=prev.patch.model_dump() if prev else None,
            previous_verification=prev.verification.model_dump() if prev and prev.verification else None,
            target_files=project.target_files,
        )
        try:
            llm_result = llm_client.generate_repair(context)
        except Exception as exc:
            code = getattr(exc, "code", "UNKNOWN")
            hint = getattr(exc, "hint", "")
            store.transition(session_id, SessionState.ERROR, f"{code}: {exc}")
            print(f"  LLM error [{code}]: {exc}")
            if hint:
                print(f"  hint: {hint}")
            return 1

        proposal = llm_result.proposal
        print(f"  model: {llm_result.model} | tokens/s: {llm_result.tokens_per_second}")
        print(f"  target: {proposal.target_file}")
        print(f"  root cause: {proposal.root_cause}")
        print(f"  explanation: {proposal.explanation}")

        validation = validate_patch(str(ws), proposal.target_file, proposal, project.target_files)
        if not validation.ok:
            store.transition(session_id, SessionState.ERROR, f"Validation failed: {validation.codes}")
            print(f"  [3/6] Validation failed: {validation.codes} — cannot apply this patch")
            return 1
        print("  [3/6] Validation: OK")
        store.transition(session_id, SessionState.PATCH_READY, "Validated")
        store.transition(session_id, SessionState.AWAITING_APPROVAL, "Awaiting user approval")

        # [4/6] show diff
        print("\n  --- DIFF (before/after) ---")
        print(validation.diff)
        print("  --- end diff ---\n")

        approved = args.auto_approve
        if not approved:
            ans = input("  Apply this patch? [y/N]: ").strip().lower()
            approved = ans == "y"
        if not approved:
            store.transition(session_id, SessionState.FAILURE_DETECTED, "Rejected by user")
            print("  Rejected by user.")
            return 0

        # [5/6] apply
        store.transition(session_id, SessionState.APPLYING_PATCH, "Applying patch")
        apply_patch(session_id, attempt, proposal.target_file, proposal, validation, workspace_root=ws)
        print("  [5/6] Patch applied (backup stored).")

        # [6/6] verify
        print("  [6/6] Verify: rerunning tests...")
        store.transition(session_id, SessionState.VERIFYING, "Verifying patch")
        verification = verifier.verify(
            ws, project.test_command, previously_failing, list(diag.passing_tests)
        )
        store.set_verdict(session_id, verification.verdict)
        print(f"  Verdict: {verification.verdict} ({verification.reason or '-'})")
        print(f"  {verification.passed} passed, {verification.failed} failed, {verification.errors} errors")
        if verification.verdict == "REPAIR_VERIFIED":
            store.transition(session_id, SessionState.REPAIR_VERIFIED, "Verified")
            verified = True
        else:
            store.transition(session_id, SessionState.REPAIR_FAILED, verification.reason or "Failed")
            if attempt >= MAX_ATTEMPTS:
                print("  Max attempts reached. Repair not verified.")

    report_path = write_report(store.get(session_id))
    print(f"Report written to: {report_path}")
    if verified:
        print("\nRepair VERIFIED by real pytest. Done.")
        return 0
    print("\nRepair FAILED or not verified. See above.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
