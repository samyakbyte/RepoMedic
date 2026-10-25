# RepoMedic Architecture

## Overview

RepoMedic is a strictly local, human-in-the-loop software repair agent consisting of:

1. **FastAPI Backend (`backend/app/`)** — Owns sandbox isolation, pytest execution, context construction, Ollama communication, AST/allowlist patch validation, atomic patch application, SHA-256 backup/rollback, verification, and session persistence.
2. **React + TypeScript + Vite Frontend (`frontend/src/`)** — Connects to `/api/*` via Vite's dev proxy, visualizes the state machine pipeline, displays pre-repair diagnostics and unified/split diffs, enforces the human approval gate, runs multi-project benchmarks, and exports reports.
3. **Demo Fixtures (`demo-projects/`)** — Three self-contained buggy Python repositories (`calculator-bug`, `inventory-bug`, `string-utils-bug`), never mutated in place.
4. **Reference Fixes (`evaluation/references/`)** — Used exclusively by `backend/tests/test_references.py` to validate fixture solvability; never imported or read by application code.

## Session State Machine

```text
IDLE ──► DIAGNOSING ──► FAILURE_DETECTED ──► GENERATING_REPAIR ──► PATCH_READY ──► AWAITING_APPROVAL
            │                  ▲                     │                                  │        │
            ▼                  └─────────────────────┼──────────────────────────────────┘        ▼
          IDLE (all pass)                            │ (reject / rollback)                 APPLYING_PATCH
                                                     │                                           │
                                                     ▼                                           ▼
                                                   ERROR                                     VERIFYING
                                                                                              /     \
                                                                                             ▼       ▼
                                                                                 REPAIR_VERIFIED   REPAIR_FAILED
```

Every transition is guarded by `SessionStore.transition()` using a per-session `threading.RLock`, recorded in `session.timeline` with UTC ISO-8601 timestamps, and atomically persisted to `data/sessions/<session_id>/session.json`.
