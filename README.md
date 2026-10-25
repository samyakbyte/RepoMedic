# RepoMedic

**Diagnose. Patch. Verify.** — An offline, human-in-the-loop AI test-repair agent for Python repositories powered by a local [Ollama](https://ollama.com) coding model (`qwen2.5-coder:1.5b`).

RepoMedic isolates failing projects in temporary sandboxes, runs `pytest` via JUnit XML diagnostics, builds a bounded repair context, asks a local Ollama model for a structured search/replace patch, validates syntax (`ast.parse`) and file allowlists before showing you a unified diff, and only writes changes (with SHA-256 backups and one-click rollback) after human approval — verifying every fix with a real `pytest` re-run.

---

## Quick Start (Windows)

### Prerequisites
1. **Python 3.10+** (`python --version`) — [python.org](https://www.python.org/downloads/) *(check "Add Python to PATH")*
2. **Node.js 18+ LTS** (`node --version` / `npm --version`) — [nodejs.org](https://nodejs.org/)
3. **Ollama** *(for offline AI patch generation)* — [ollama.com/download](https://ollama.com/download)
   ```bat
   ollama pull qwen2.5-coder:1.5b
   ```

### 1. Install Dependencies (Once)
Double-click **`setup.bat`** (or run `setup.bat` in Command Prompt).
- Creates `backend\.venv` and installs FastAPI, Uvicorn, Pydantic, HTTPX, Pytest, and Ruff.
- Runs `npm install` inside `frontend\`.

### 2. Launch RepoMedic
Double-click **`start.bat`** (or run `start.bat` in Command Prompt).
- Starts Ollama (if installed and not already running), Backend API (`http://127.0.0.1:8000`), and React Web UI (`http://localhost:5173`).
- Automatically opens **`http://localhost:5173`** once the frontend server is ready.

---

## Manual Start (macOS / Linux / Windows Terminal)

### Terminal 1 — Backend (`:8000`)
```bash
python3 -m venv backend/.venv
source backend/.venv/bin/activate   # Windows CMD: backend\.venv\Scripts\activate.bat
pip install -r backend/requirements.txt
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Terminal 2 — Frontend (`:5173`)
```bash
cd frontend
npm install
npm run dev
```

Open **`http://localhost:5173`** (API docs at **`http://localhost:8000/docs`**).

---

## Architecture & Key Features

| Layer | Location | Highlights |
|---|---|---|
| **Sandbox & Security** | `backend/app/core/security.py`, `workspace.py` | Copies demo fixtures into `data/workspaces/<session_id>/`; blocks path traversal, drive/UNC paths, null bytes, symlinks, and test-file tampering; scrubs secrets from subprocess environments. |
| **Diagnostics** | `backend/app/core/diagnostics.py` | Runs `[sys.executable, "-m", "pytest"]` with timeout process-tree cleanup and parses JUnit XML into structured failure records. |
| **Bounded Context** | `backend/app/core/context.py` | Builds a `<6000` char prompt with failing test assertions, short tracebacks, test source, and `src/` files — never reading `evaluation/references/`. |
| **Offline LLM Client** | `backend/app/core/llm.py` | Talks strictly to local Ollama (`/api/chat`), enforces `RepairProposal` JSON schema with bounded validation retries, and reports native token/s telemetry. |
| **Patch Engine** | `backend/app/core/patching.py` | Validates allowlist, uniqueness (exact + CRLF normalization fallback), non-noop, `ast.parse` syntax, SHA-256 backup, atomic temp-file swap, and instant rollback. |
| **State Machine & API** | `backend/app/core/state_machine.py`, `backend/app/api/` | Thread-safe `RLock` state machine persisted to `data/sessions/` with full audit timeline and JSON/Markdown report export. |
| **React Dashboard** | `frontend/src/` | Repair Studio (project cards, live state pipeline, workspace inspector, unified & split diff viewer, human approval gate), Benchmarks sweep runner, and Session History. |

---

## Running Tests

```bash
cd backend
.venv/bin/python -m pytest -v
```

All **60 backend unit & API integration tests** run offline (including mocked-Ollama end-to-end repair/approve/verify/rollback tests).

---

## Documentation

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — System architecture & state machine transitions
- [`docs/SECURITY.md`](docs/SECURITY.md) — Sandbox boundaries, path resolution, & protected files
- [`docs/SETUP.md`](docs/SETUP.md) — Detailed setup & environment variables
- [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md) — Common Windows, Ollama, & port issues
- [`docs/BUILD_LOG.md`](docs/BUILD_LOG.md) — Phase-by-phase build & verification record
