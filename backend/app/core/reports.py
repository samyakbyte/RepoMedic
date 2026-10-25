"""Report generation: JSON report per session."""

import os
from pathlib import Path

from app.config import REPORTS_DIR
from app.schemas.session import SessionDetail


def build_report_path(session_id: str) -> Path:
    return REPORTS_DIR / f"{session_id}.json"


def write_report(session: SessionDetail) -> Path:
    path = build_report_path(session.id)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(session.model_dump_json(indent=2), encoding="utf-8")
    os.replace(tmp, path)
    session.report_path = str(path)
    return path
