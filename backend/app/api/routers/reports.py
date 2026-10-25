"""Report download endpoint (mirror of sessions/{id}/report)."""

from fastapi import APIRouter
from fastapi.responses import FileResponse

from app.app_core import store
from app.config import REPORTS_DIR
from app.core.reports import write_report
from app.schemas.common import ApiError

router = APIRouter()


@router.get("/{session_id}")
def get_report(session_id: str, format: str = "json"):
    session = store.get(session_id)  # 404 if missing
    report_path = REPORTS_DIR / f"{session_id}.json"
    if not report_path.exists():
        write_report(session)
    if format == "md":
        from fastapi.responses import PlainTextResponse

        markdown = _markdown_report(session)
        return PlainTextResponse(markdown, media_type="text/markdown")
    return FileResponse(report_path, media_type="application/json", filename=f"{session_id}.json")


def _markdown_report(session) -> str:
    lines = [f"# RepoMedic Report: {session.id}", ""]
    lines.append(f"- Project: {session.project_id}")
    lines.append(f"- State: {session.state}")
    lines.append(f"- Verdict: {session.verdict or '-'}")
    lines.append(f"- Attempts: {session.attempt}/{session.max_attempts}")
    lines.append("")
    lines.append("## Timeline")
    for entry in session.timeline:
        lines.append(f"- {entry.at}  {entry.state}" + (f" — {entry.note}" if entry.note else ""))
    return "\n".join(lines)
