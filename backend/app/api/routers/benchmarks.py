"""Benchmark endpoints: start a diagnose->generate->approve->verify sweep across projects."""

import asyncio
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.app_core import BENCHMARK_RESULTS_DIR, llm_client, workspace_manager
from app.core.benchmark import BenchmarkRunner

router = APIRouter()

_runner = BenchmarkRunner(workspace_manager, llm_client)


class BenchmarkRunBody(BaseModel):
    runs_per_project: int = Field(3, ge=1, le=10)
    model: Optional[str] = Field(None, description="Ollama model; defaults to configured model")
    project_ids: Optional[list[str]] = Field(None, description="Subset of project ids; default all")


@router.post("/run", status_code=202)
def run_benchmark(body: BenchmarkRunBody):
    projects = workspace_manager.list_projects()
    if body.project_ids:
        wanted = set(body.project_ids)
        projects = [p for p in projects if p.id in wanted]
        if not projects:
            from app.schemas.common import ApiError

            raise ApiError("UNKNOWN_PROJECT", "None of the requested project ids exist", "Call GET /api/projects for the list")

    model = body.model or llm_client.model
    job = _runner.start(model, body.runs_per_project)
    # Benchmark jobs are blocking (subprocess + LLM); run in a worker thread.
    asyncio.create_task(_async_run(job, projects))
    return {"job_id": job.job_id, "status": "running", "model": model, "runs_per_project": body.runs_per_project}


async def _async_run(job, projects):
    await asyncio.to_thread(_runner.run, job, projects)
    _runner.save_results(job)  # writes benchmarks/results/<ts>_<model>.json (+ summary.md)


@router.get("")
def list_benchmarks():
    return [_job_summary(j) for j in _runner._jobs.values()]


@router.get("/{job_id}")
def get_benchmark(job_id: str):
    job = _runner.get(job_id)
    if job is None:
        from app.schemas.common import ApiError

        raise ApiError("NOT_FOUND", f"Benchmark job not found: {job_id}", status_code=404)
    return job.to_dict()


def _job_summary(job) -> dict:
    return {
        "job_id": job.job_id,
        "model": job.model,
        "status": job.status,
        "created_at": job.created_at,
        "finished_at": job.finished_at,
        "runs": len(job.results),
        "summary": job.summary,
    }
