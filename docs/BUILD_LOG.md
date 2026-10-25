# RepoMedic Build Log

Honest record of what was built, fixed, and verified across phases.

## Phase 0 — Skill discovery

| Skill target | Status | Notes |
|---|---|---|
| Agent skills (Arena built-in) | already present | Built-in workspace, bash, and process tools used |
| npm / Python packages | installed via package managers | Verified via `pip install` and `npm install` |
| UI/UX Pro Max | not available | Tailwind design system configured directly in `frontend/` |
| Anime.js | installed (`animejs@^3.2.2`) | Used in `StatePipeline.tsx` for state step transitions |

## Phase 1 — Environment setup
- Python `3.11.2`, pytest `8.3.0`, FastAPI `0.115.0`, Node.js + Vite `5.4.21` verified in sandbox.
- Created `.env.example`, `setup.bat`, `start.bat`, and `.gitignore` runtime exclusions (`data/`, `.venv/`, `node_modules/`, `frontend/dist/`, `*.zip`).

## Phase 2 — Core engine
- Implemented `security.py`, `workspace.py`, `diagnostics.py`, `context.py`, `llm.py`, `patching.py`, `verification.py`, `state_machine.py`, `reports.py`, `benchmark.py`, and `scripts/repair_cli.py`.
- Key bugs caught & fixed during verification:
  - Replaced non-reentrant `threading.Lock` with `threading.RLock` in `SessionStore` to eliminate `transition() -> get()` deadlock.
  - Updated `ContextBuilder` to automatically include workspace `src/**/*.py` target files (not just JUnit test files) so the model receives the buggy source code.
  - Updated `patching.py` to support exact substring matching + CRLF/trailing-whitespace line fallback + multi-layout workspace resolution (`data/workspaces/<sid>/<project_id>`).
  - Updated `Verifier.verify()` so test failure reasons (`REGRESSION`, `ORIGINAL_STILL_FAILING`) are evaluated before generic `exit_code != 0`.
  - Fixed `NO_TESTS_COLLECTED` detection when pytest writes an empty JUnit XML with exit code 5.

## Phase 3 — API
- Mounted `/api/health`, `/api/model/status`, `/api/projects`, `/api/sessions/*` (including `/files`, `/diagnose`, `/repair`, `/patch`, `/approve`, `/reject`, `/rollback`, `/reset`, `/report`), `/api/benchmarks/*`, and `/api/reports/*`.
- Switched background jobs to FastAPI `BackgroundTasks` threadpool functions and added missing `APPLYING_PATCH -> VERIFYING` transition in `_run_apply_verify_sync`.

## Phase 4 & 5 — Frontend & Integration
- Built React 18 + TypeScript + Vite + Tailwind CSS + Lucide + Anime.js SPA in `frontend/`:
  - `TopNav`, `StatePipeline`, `ProjectSelector`, `DiagnosticsPanel`, `PatchReviewPanel` (unified & split diff + human approval gate), `VerificationPanel`, `TimelinePanel`, `RepairStudioPage`, `BenchmarksPage`, and `HistoryPage`.
  - Configured Vite dev/preview proxy (`/api -> http://127.0.0.1:8000`) and verified production build (`npm run build` -> 0 errors).
- Fixed Windows `setup.bat` (`call npm.cmd install`) and `start.bat` (safe `%LOCALAPPDATA%\Programs\Ollama\ollama.exe` check + port readiness wait).

## Phase 6 — Testing
- `backend/.venv/bin/python -m pytest -v`: **60 passed, 0 failed** (including full E2E session repair/approve/verify/rollback with mocked Ollama).
- `cd frontend && npm run build`: **PASS** (`tsc -b && vite build`).

## Phase 7 — Model selection and benchmarks
- Default model configured to `qwen2.5-coder:1.5b` via Ollama (`http://127.0.0.1:11434`).
- Real Ollama inference is UNTESTED in this cloud sandbox (no local Ollama daemon); run `ollama pull qwen2.5-coder:1.5b` locally and launch the **Benchmarks** tab to execute live sweeps.

## Phase 8 & 9 — Documentation & Audit
- Completed `README.md`, `docs/ARCHITECTURE.md`, `docs/SECURITY.md`, `docs/SETUP.md`, `docs/TROUBLESHOOTING.md`, and `docs/BUILD_LOG.md`.
- Audit summary: Core Engine **PASS**, Security **PASS**, FastAPI Routes **PASS**, React Frontend Build **PASS**, Unit/Integration Suite (60/60) **PASS**, Live Ollama Hardware Benchmark **UNTESTED in sandbox (ready for local Windows run)**.
