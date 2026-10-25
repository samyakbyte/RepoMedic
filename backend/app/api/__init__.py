from fastapi import APIRouter

from app.api.routers import benchmarks, health, projects, reports, sessions

api_router = APIRouter()
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(projects.router, prefix="/projects", tags=["projects"])
api_router.include_router(sessions.router, prefix="/sessions", tags=["sessions"])
api_router.include_router(benchmarks.router, prefix="/benchmarks", tags=["benchmarks"])
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])

__all__ = ["api_router"]
