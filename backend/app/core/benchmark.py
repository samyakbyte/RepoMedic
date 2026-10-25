"""Benchmark orchestrator: diagnose -> generate -> auto-approve -> verify across projects x runs."""

from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.app_core import BENCHMARK_RESULTS_DIR
from app.config import MAX_ATTEMPTS as MAX_ATTEMPTS_CFG
from app.core.context import ContextBuilder
from app.core.diagnostics import run_pytest
from app.core.llm import OllamaClient, OllamaError
from app.core.patching import apply_patch, validate_patch
from app.core.workspace import WorkspaceManager


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class BenchmarkJob:
    def __init__(self, job_id: str, model: str, runs_per_project: int):
        self.job_id = job_id
        self.model = model
        self.runs_per_project = runs_per_project
        self.status = "running"  # running | done | failed
        self.created_at = _now()
        self.finished_at: Optional[str] = None
        self.results: list = []
        self.summary: dict = {}

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "model": self.model,
            "runs_per_project": self.runs_per_project,
            "status": self.status,
            "created_at": self.created_at,
            "finished_at": self.finished_at,
            "results": self.results,
            "summary": self.summary,
        }


class BenchmarkRunner:
    def __init__(self, workspace_manager: WorkspaceManager, client: OllamaClient):
        self.workspace_manager = workspace_manager
        self.client = client
        self.context_builder = ContextBuilder()
        self._jobs: dict = {}

    def start(self, model: str, runs_per_project: int) -> BenchmarkJob:
        job_id = "bench-" + datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
        job = BenchmarkJob(job_id, model, runs_per_project)
        self._jobs[job_id] = job
        return job

    def get(self, job_id: str):
        return self._jobs.get(job_id)

    def run(self, job: BenchmarkJob, projects: list) -> None:
        try:
            all_results = []
            for project in projects:
                for run in range(1, job.runs_per_project + 1):
                    res = self._run_once(project, run, job.model)
                    all_results.append(res)
            job.results = all_results
            job.summary = self._summarize(all_results, job.model)
            job.status = "done"
        except Exception as exc:  # noqa: BLE001
            job.status = "failed"
            job.summary = {"error": str(exc)}
        finally:
            job.finished_at = _now()

    def _run_once(self, project, run: int, model: str) -> dict:
        session_id = uuid.uuid4().hex[:8] + "-" + project.id + "-run" + str(run)
        ws = self.workspace_manager.create_workspace(session_id, project.id)
        started = time.perf_counter()

        record = {
            "project": project.id,
            "bug_category": project.bug_category,
            "model": model,
            "run": run,
            "attempt": 0,
            "initial_failed": 0,
            "initial_passed": 0,
            "initial_errors": 0,
            "final_passed": 0,
            "final_failed": 0,
            "final_errors": 0,
            "original_failure_resolved": False,
            "regressions": False,
            "patch_validation_ok": False,
            "validation_codes": [],
            "attempts_used": 0,
            "generation_time_s": None,
            "verification_time_s": None,
            "total_time_s": None,
            "eval_count": None,
            "eval_duration_ns": None,
            "tokens_per_second": None,
            "outcome": "ERROR",
            "error": None,
            "workspace": str(ws),
        }

        try:
            diag = run_pytest(ws, project.test_command, timeout_s=30.0)
            record["initial_failed"] = diag.failed
            record["initial_passed"] = diag.passed
            record["initial_errors"] = diag.errors

            if diag.failed == 0 and diag.errors == 0 and diag.error_type is None:
                record["outcome"] = "NO_FAILURE_FOUND"
                return record

            failing_ids = [f.test_id for f in diag.failures]
            context = self.context_builder.build(
                str(ws),
                diag,
                failing_ids[0] if failing_ids else project.failing_test,
                project.name,
                project.description,
            )

            attempt = 0
            verified = False
            while attempt < MAX_ATTEMPTS_CFG:
                attempt += 1
                record["attempt"] = attempt
                gen_start = time.perf_counter()
                try:
                    llm_result = self.client.generate_repair(context)
                except OllamaError as exc:
                    record["error"] = exc.code + ": " + exc.message
                    record["outcome"] = "LLM_ERROR"
                    break
                gen_time = time.perf_counter() - gen_start
                record["generation_time_s"] = gen_time
                record["eval_count"] = llm_result.eval_count
                record["eval_duration_ns"] = llm_result.eval_duration_ns
                record["tokens_per_second"] = llm_result.tokens_per_second

                proposal = llm_result.proposal
                validation = validate_patch(str(ws), proposal.target_file, proposal, project.target_files)
                record["patch_validation_ok"] = validation.ok
                record["validation_codes"] = validation.codes

                if not validation.ok:
                    context += (
                        "\n--- PREVIOUS PATCH REJECTED BY VALIDATION ---\n"
                        f"codes: {validation.codes}\n"
                        "Reply with a corrected patch that satisfies the schema and validation rules."
                    )
                    if attempt >= MAX_ATTEMPTS_CFG:
                        record["outcome"] = "VALIDATION_FAILED"
                    continue

                apply_patch(session_id, attempt, proposal.target_file, proposal, validation)

                ver_start = time.perf_counter()
                verification = self._verify(ws, project, diag.failures)
                record["verification_time_s"] = time.perf_counter() - ver_start
                record["final_passed"] = verification.passed
                record["final_failed"] = verification.failed
                record["final_errors"] = verification.errors
                record["original_failure_resolved"] = len(verification.originally_failing_now_passing) > 0
                record["regressions"] = len(verification.regressions) > 0

                if verification.verdict == "REPAIR_VERIFIED":
                    record["outcome"] = "VERIFIED"
                    verified = True
                    break
                else:
                    record["outcome"] = "VERIFICATION_FAILED:" + (verification.reason or "unknown")
                    context += (
                        "\n--- PREVIOUS PATCH FAILED VERIFICATION ---\n"
                        f"reason: {verification.reason}\n"
                        f"still failing: {verification.originally_failing_now_passing}\n"
                        f"regressions: {verification.regressions}\n"
                        f"output: {verification.raw_output[:1500]}\n"
                        "Reply with a corrected patch."
                    )
                    if attempt >= MAX_ATTEMPTS_CFG:
                        break

            record["attempts_used"] = attempt
            if not verified and record["outcome"] == "ERROR":
                record["outcome"] = "UNKNOWN"
        except Exception as exc:  # noqa: BLE001
            record["error"] = str(exc)
            record["outcome"] = "EXCEPTION"
        finally:
            record["total_time_s"] = time.perf_counter() - started
            self.workspace_manager.cleanup(session_id)
        return record

    def _verify(self, ws, project, previous_failures):
        from app.core.verification import Verifier

        previously_failing = [f.test_id for f in previous_failures]
        verifier = Verifier(timeout_s=30.0)
        return verifier.verify(str(ws), project.test_command, previously_failing, [])

    def _summarize(self, results: list, model: str) -> dict:
        total = len(results)
        verified = sum(1 for r in results if r["outcome"] == "VERIFIED")
        first_attempt = [r for r in results if r["attempts_used"] == 1]
        first_ok = sum(1 for r in first_attempt if r["outcome"] == "VERIFIED")
        gen_times = [r["generation_time_s"] for r in results if r["generation_time_s"] is not None]
        toks = [r["tokens_per_second"] for r in results if r["tokens_per_second"] is not None]

        def avg(xs):
            return round(sum(xs) / len(xs), 3) if xs else None

        def median(xs):
            if not xs:
                return None
            s = sorted(xs)
            n = len(s)
            return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2

        return {
            "model": model,
            "total_runs": total,
            "verified_runs": verified,
            "success_rate": round(verified / total, 3) if total else 0,
            "first_attempt_success_rate": round(first_ok / len(first_attempt), 3) if first_attempt else 0,
            "mean_generation_time_s": avg(gen_times),
            "median_generation_time_s": median(gen_times),
            "mean_tokens_per_second": avg(toks),
            "hardware": _hardware_note(),
        }

    def save_results(self, job: BenchmarkJob) -> Path:
        BENCHMARK_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        safe_model = job.model.replace(":", "_").replace("/", "_")
        path = BENCHMARK_RESULTS_DIR / f"{ts}_{safe_model}.json"
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps(job.to_dict(), indent=2), encoding="utf-8")
        os.replace(tmp, path)
        self._write_summary_md(job)
        return path

    def _write_summary_md(self, job: BenchmarkJob) -> None:
        BENCHMARK_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        path = BENCHMARK_RESULTS_DIR / "summary.md"
        s = job.summary or {}
        lines = [
            f"# Benchmark summary: {job.model}",
            f"- Job: {job.job_id}",
            f"- Status: {job.status}",
            f"- Total runs: {s.get('total_runs', 0)}",
            f"- Verified runs: {s.get('verified_runs', 0)}",
            f"- Success rate: {s.get('success_rate', 0)}",
            f"- First-attempt success rate: {s.get('first_attempt_success_rate', 0)}",
            f"- Mean generation time (s): {s.get('mean_generation_time_s', 0)}",
            f"- Median generation time (s): {s.get('median_generation_time_s', 0)}",
            f"- Mean tokens/sec: {s.get('mean_tokens_per_second', 0)}",
            f"- Hardware: {s.get('hardware', 'n/a')}",
            "",
            "## Per-run results",
            "| project | run | outcome | attempts | gen_time_s | tok/s | validation | error |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for r in job.results:
            lines.append(
                f"| {r['project']} | {r['run']} | {r['outcome']} | {r['attempts_used']} | "
                f"{r['generation_time_s']} | {r['tokens_per_second']} | {r['validation_codes']} | {r['error'] or '-'} |"
            )
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _hardware_note() -> str:
    try:
        import subprocess  # noqa: PLC0415

        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if out.returncode == 0 and out.stdout.strip():
            return "nvidia-smi: " + out.stdout.strip().replace("\n", "; ")
    except Exception:
        pass
    return "nvidia-smi unavailable (CPU/no-GPU environment)"
