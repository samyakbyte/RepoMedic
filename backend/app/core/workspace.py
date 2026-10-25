"""Workspace manager: demo project listing, isolated workspace copies, fixture integrity."""

import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Optional

from app.config import DATA_DIR, WORKSPACES_DIR
from app.core.security import SecurityError
from app.schemas.project import Project

IGNORED_NAMES = {"__pycache__", ".pytest_cache", ".git", ".repomedic"}


class WorkspaceManager:
    def __init__(self, demo_projects_dir: str | Path):
        self.demo_projects_dir = Path(demo_projects_dir)
        self._fixture_hashes: dict[str, str] = {}

    # ---- project listing -------------------------------------------------

    def list_projects(self) -> list[Project]:
        projects: list[Project] = []
        if not self.demo_projects_dir.exists():
            return projects
        for entry in sorted(self.demo_projects_dir.iterdir()):
            if not entry.is_dir() or entry.is_symlink():
                continue
            project_json = entry / "project.json"
            if not project_json.exists():
                continue
            try:
                data = json.loads(project_json.read_text(encoding="utf-8"))
                projects.append(Project(**data))
            except Exception:
                # Skip malformed project definitions rather than crashing.
                continue
        return projects

    def get_project(self, project_id: str) -> Optional[Project]:
        for project in self.list_projects():
            if project.id == project_id:
                return project
        return None

    # ---- fixture integrity ----------------------------------------------

    def record_fixture_hashes(self) -> dict[str, str]:
        """Hash every file under demo-projects (excluding caches). Call at startup."""
        hashes: dict[str, str] = {}
        for root, dirs, files in os.walk(self.demo_projects_dir):
            dirs[:] = [d for d in dirs if d not in IGNORED_NAMES]
            for name in files:
                path = Path(root) / name
                if path.is_symlink():
                    continue
                rel = path.relative_to(self.demo_projects_dir).as_posix()
                hashes[rel] = sha256_file(path)
        self._fixture_hashes = hashes
        return hashes

    def verify_fixtures_unchanged(self) -> list[str]:
        """Return list of fixture files whose hash changed since record_fixture_hashes."""
        changed: list[str] = []
        for rel, expected in self._fixture_hashes.items():
            path = self.demo_projects_dir / rel
            if not path.exists():
                changed.append(rel + " (missing)")
                continue
            if path.is_symlink():
                changed.append(rel + " (became symlink)")
                continue
            if sha256_file(path) != expected:
                changed.append(rel)
        return changed

    # ---- workspace creation / isolation ---------------------------------

    def create_workspace(self, session_id: str, project_id: str) -> Path:
        """Copy a demo project into data/workspaces/<session_id>/<project_id>/.

        The original fixture is never touched. Rejects projects that are or
        contain symlinks. __pycache__, .pytest_cache, .git are excluded.
        """
        src = self.demo_projects_dir / project_id
        if src.is_symlink():
            raise SecurityError("SYMLINK_PROJECT", f"Project is a symlink: {project_id}", "Use a regular directory")

        project = self.get_project(project_id)
        if project is None:
            raise SecurityError("UNKNOWN_PROJECT", f"Unknown project: {project_id}", "Pick a project from GET /api/projects")

        dst = WORKSPACES_DIR / session_id / project_id
        if dst.exists():
            shutil.rmtree(dst)
        dst.mkdir(parents=True, exist_ok=True)

        self._copy_tree(src, dst)
        return dst

    def reset_workspace(self, session_id: str, project_id: str) -> Path:
        """Remove and recreate a clean workspace copy for a session."""
        return self.create_workspace(session_id, project_id)

    def cleanup(self, session_id: str) -> None:
        ws = WORKSPACES_DIR / session_id
        if ws.exists():
            shutil.rmtree(ws, ignore_errors=True)

    # ---- internals -------------------------------------------------------

    def _copy_tree(self, src: Path, dst: Path) -> None:
        for root, dirs, files in os.walk(src):
            root_path = Path(root)
            # Reject symlinked directories
            for d in list(dirs):
                if (root_path / d).is_symlink():
                    raise SecurityError("SYMLINK_REJECTED", f"Project contains a symlink: {root_path / d}", "Remove symlinks from demo projects")
            dirs[:] = [d for d in dirs if d not in IGNORED_NAMES]
            rel_root = Path(os.path.relpath(root, src))
            target_dir = dst / rel_root if str(rel_root) != "." else dst
            target_dir.mkdir(parents=True, exist_ok=True)
            for name in files:
                src_file = root_path / name
                if src_file.is_symlink():
                    raise SecurityError("SYMLINK_REJECTED", f"Project contains a symlink: {src_file}", "Remove symlinks from demo projects")
                if name in IGNORED_NAMES:
                    continue
                shutil.copy2(src_file, target_dir / name)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()
