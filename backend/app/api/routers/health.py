"""Health and model-status endpoints."""

from fastapi import APIRouter

from app.app_core import llm_client
from app.config import APP_VERSION

router = APIRouter()


@router.get("")
def health():
    return {"status": "ok", "version": APP_VERSION}


@router.get("/model/status")
def model_status():
    return llm_client.health()
