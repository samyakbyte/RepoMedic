"""Workspace manager: project listing, isolated copies, fixture integrity."""

import json
from pathlib import Path

import pytest

from app.core.security import SecurityError
from app.core.workspace import WorkspaceManager, sha256_file

DEMO_DIR = Path(__file__).resolve().parent.parent.parent / "demo-projects"


@pytest.fixture
def manager():
    return WorkspaceManager(DEMO_DIR)


def test_list_projects(manager):
    projects = manager.list_projects()
    ids = {p.id for p in projects}
    assert ids == {"calculator-bug", "inventory-bug", "string-utils-bug"}
    for p in projects:
        assert p.name and p.description and p.test_command and p.target_files


def test_get_project(manager):
    p = manager.get_project("calculator-bug")
    assert p is not None and p.id == "calculator-bug"
    assert manager.get_project("nope") is None


def test_workspace_copy_is_isolated(manager, tmp_path):
    # Workspace copy can be modified without touching the fixture.
    ws = manager.create_workspace("session-iso", "calculator-bug")
    calc = ws / "src" / "calc.py"
    original = sha256_file(DEMO_DIR / "calculator-bug" / "src" / "calc.py")
    calc.write_text("tampered\n", encoding="utf-8")
    assert sha256_file(DEMO_DIR / "calculator-bug" / "src" / "calc.py") == original
    assert sha256_file(calc) != original
    manager.cleanup("session-iso")


def test_fixture_hashes_stable(manager):
    before = manager.record_fixture_hashes()
    assert before
    changed = manager.verify_fixtures_unchanged()
    assert changed == [], f"fixtures changed: {changed}"


def test_symlink_project_rejected(tmp_path):
    # A project dir that is a symlink must be rejected.
    real = tmp_path / "real-proj"
    real.mkdir()
    (real / "project.json").write_text(json.dumps({
        "id": "sym-proj", "name": "S", "description": "d", "bug_category": "x",
        "failing_test": "t", "target_files": ["src/x.py"]}, indent=2))
    (real / "src").mkdir()
    link = tmp_path / "link-proj"
    link.symlink_to(real)
    mgr = WorkspaceManager(tmp_path)
    with pytest.raises(SecurityError) as exc:
        mgr.create_workspace("session-sym", "link-proj")
    assert exc.value.code == "SYMLINK_PROJECT"
