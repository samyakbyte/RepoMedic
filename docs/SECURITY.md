# Security Model

RepoMedic treats all LLM output and repository execution as untrusted:

1. **Workspace Isolation (`workspace.py`)**
   - Every session operates on a fresh copy under `data/workspaces/<session_id>/<project_id>/`.
   - Symlinked projects, directories, or files are rejected (`SYMLINK_PROJECT`, `SYMLINK_REJECTED`).
   - Startup records SHA-256 hashes of every file in `demo-projects/` to guarantee fixtures remain untouched.

2. **Safe Path Resolution (`security.py`)**
   - Rejects empty paths, null bytes, absolute POSIX/Windows paths, Windows drive letters (`C:\`), UNC paths (`\\server\share`), `..` traversal segments, and symlink components.
   - Verifies `resolved.relative_to(workspace_root)` before any read or write.

3. **Protected Test & Config Files (`is_patchable`)**
   - Blocks modifications to `tests/**`, `test_*.py`, `*_test.py`, `conftest.py`, `pytest.ini`, `project.json`, `pyproject.toml`, `requirements*.txt`, and non-`.py` files.
   - Enforces the per-project `target_files` allowlist from `project.json`.

4. **Subprocess Hardening (`diagnostics.py`)**
   - Never shells out (`shell=False`); runs `[sys.executable, "-m", "pytest", ...]`.
   - Scrubs environment variables containing `KEY`, `TOKEN`, `SECRET`, `PASSWORD`, `AUTH`, or `CREDENTIAL`.
   - Enforces `PYTEST_TIMEOUT_S` and kills the entire process group/tree on timeout.

5. **Human-in-the-Loop Gate**
   - Patches are validated with `ast.parse` (plus optional `ruff --select E9`) and staged in `AWAITING_APPROVAL`. No workspace file is modified until `POST /api/sessions/{id}/approve`.
