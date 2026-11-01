"""Authentication and authorization dependencies for Supabase JWT verification."""

from typing import Annotated
from uuid import UUID

import jwt
from backend.app.core.config import PLACEHOLDERS, Settings, get_settings
from backend.app.core.errors import (
    ForbiddenError,
    NotFoundError,
    ServiceUnavailableError,
    UnauthorizedError,
)
from backend.app.database.models import Job, Report
from backend.app.database.session import get_db
from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def get_current_user_id(
    authorization: Annotated[str | None, Header()] = None,
    settings: Annotated[Settings, Depends(get_settings)] = None,
) -> UUID:
    """Verify Supabase JWT token and extract the authenticated user UUID.

    Client-supplied user IDs in headers or request bodies are strictly rejected.
    Identity is solely derived from verified cryptographic signatures.
    """
    if not authorization:
        raise UnauthorizedError("Missing Authorization header")

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise UnauthorizedError("Invalid Authorization format. Expected: Bearer <token>")

    token = parts[1]
    cfg = settings or get_settings()

    if (not cfg.SUPABASE_JWT_SECRET or len(cfg.SUPABASE_JWT_SECRET.strip()) < 32
            or any(value in cfg.SUPABASE_JWT_SECRET.lower() for value in PLACEHOLDERS)):
        raise ServiceUnavailableError("Authentication is not configured.")

    try:
        # Decode and verify Supabase JWT
        # Supabase default tokens use HS256 with project JWT secret
        payload = jwt.decode(
            token,
            cfg.SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated",
            issuer=f"{cfg.SUPABASE_URL.rstrip('/')}/auth/v1",
            options={"require": ["exp", "sub", "aud", "iss"]},
        )
        if payload.get("role") != "authenticated":
            raise UnauthorizedError("A citizen access token is required.")
        user_id_str = payload.get("sub")
        if not user_id_str:
            raise UnauthorizedError("Token missing 'sub' claim")
        return UUID(user_id_str)
    except jwt.ExpiredSignatureError:
        raise UnauthorizedError("Session expired. Please sign in again.") from None
    except jwt.InvalidTokenError:
        raise UnauthorizedError("Invalid authentication token") from None
    except ValueError:
        raise UnauthorizedError("Token 'sub' claim is not a valid UUID") from None


async def require_report_owner(
    report_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Report:
    """Verify report exists and caller is the owner."""
    query = select(Report).where(Report.id == report_id)
    result = await db.execute(query)
    report = result.scalar_one_or_none()

    if not report:
        raise NotFoundError("Report not found")
    if report.owner_id != user_id:
        raise ForbiddenError("You do not have permission to view or modify this report")
    return report


async def require_job_owner(
    job_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Job:
    """Verify job exists and caller is the owner."""
    query = select(Job).where(Job.id == job_id)
    result = await db.execute(query)
    job = result.scalar_one_or_none()

    if not job:
        raise NotFoundError("Job not found")
    if job.owner_id != user_id:
        raise ForbiddenError("You do not have permission to inspect this job")
    return job
