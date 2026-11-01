"""Liveness and readiness health endpoints."""

from backend.app.core.config import Settings, get_settings
from backend.app.database.session import get_db
from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(tags=["Health"])


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
        details["database"] = "connected"
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
        "ready": False,  # Worker/checkpoint integration is not operational yet.
        "details": details,
    }
