"""Project listing endpoint."""

from fastapi import APIRouter

from app.app_core import workspace_manager

router = APIRouter()


@router.get("")
def list_projects():
    return workspace_manager.list_projects()
