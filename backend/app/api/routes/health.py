"""Liveness and readiness health endpoints."""

from datetime import timedelta

from backend.app.core.config import Settings, get_settings
from backend.app.database.models import Job, WorkerHeartbeat, utc_now
from backend.app.database.session import get_db
from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(tags=["Health"])


@router.get("/health/live", summary="Process liveness; no external calls")
async def liveness():
    return {"live": True}


@router.get(
    "/health",
    summary="Check service health and readiness",
    description="Reports API liveness, configuration validity, and database connectivity.",
)
async def health_check(
    request: Request,
    settings: Settings = Depends(get_settings),
    db: AsyncSession = Depends(get_db),
):
    """Liveness and readiness check. Returns 503 if configuration is invalid or database unreachable."""
    details = {
        "environment": settings.ENVIRONMENT,
        "database": "unknown",
        "configuration": "valid" if settings.is_configured_for_production() else "invalid_or_placeholder",
    }

    if not settings.is_configured_for_production() and settings.ENVIRONMENT == "production":
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "request_id": request.state.request_id,
                "code": "service_unavailable",
                "message": "Production environment has unconfigured placeholder credentials",
                "details": details,
            },
        )

    try:
        await db.execute(text("SELECT 1"))
        await db.execute(select(Job).limit(0))
        details["database"] = "connected"
        fresh_worker = (await db.execute(select(WorkerHeartbeat.worker_id).where(
            WorkerHeartbeat.last_seen > utc_now() - timedelta(seconds=45)
        ).limit(1))).scalar_one_or_none()
        details["worker"] = "recent_heartbeat" if fresh_worker else "unavailable"
    except Exception:
        details["database"] = "unreachable"
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "request_id": request.state.request_id,
                "code": "database_unavailable",
                "message": "Database is unreachable or uninitialized",
                "details": details,
            },
        )

    return {
        "status": "healthy",
        "live": True,
        "ready": bool(fresh_worker) and (settings.ENVIRONMENT != "production" or settings.is_configured_for_production()),
        "details": details,
    }


@router.get("/health/ready", summary="Database schema and recent initialized-worker readiness")
async def readiness(request: Request, settings: Settings = Depends(get_settings), db: AsyncSession = Depends(get_db)):
    result = await health_check(request, settings, db)
    if isinstance(result, JSONResponse):
        return result
    if not result["ready"]:
        return JSONResponse(status_code=503, content={"code": "service_unavailable",
            "message": "No recently initialized worker is available.",
            "request_id": request.state.request_id, "details": result["details"]})
    return result
