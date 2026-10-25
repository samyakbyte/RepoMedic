"""RepoMedic FastAPI application."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import api_router
from app.config import APP_VERSION, CORS_ORIGINS
from app.schemas.common import ApiError, ErrorBody, ErrorResponse

app = FastAPI(title="RepoMedic", version=APP_VERSION, description="Diagnose. Patch. Verify. — offline AI test-repair agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ApiError)
async def api_error_handler(request, exc: ApiError):
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error=ErrorBody(code=exc.code, message=exc.message, hint=exc.hint, state=exc.state)
        ).model_dump(),
    )


@app.on_event("startup")
def startup():
    from app.app_core import workspace_manager

    workspace_manager.record_fixture_hashes()


app.include_router(api_router, prefix="/api")
