"""Authentication and authorization dependencies for Supabase JWT verification."""

import asyncio
from functools import lru_cache
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


@lru_cache(maxsize=4)
def project_jwks(url: str):
    """Cache only the configured project's public keys for at most five minutes."""
    return jwt.PyJWKClient(url, lifespan=300, timeout=5)


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

    try:
        header = jwt.get_unverified_header(token)
        algorithm = header.get("alg")
        if algorithm == "HS256":
            if (not cfg.SUPABASE_JWT_SECRET or len(cfg.SUPABASE_JWT_SECRET.strip()) < 32
                    or any(value in cfg.SUPABASE_JWT_SECRET.lower() for value in PLACEHOLDERS)):
                raise ServiceUnavailableError("Legacy authentication is not configured.")
            key = cfg.SUPABASE_JWT_SECRET
        elif algorithm in ("ES256", "RS256"):
            if not header.get("kid") or not cfg.SUPABASE_URL.startswith("https://"):
                raise UnauthorizedError("Invalid authentication signing key")
            client = project_jwks(f"{cfg.SUPABASE_URL.rstrip('/')}/auth/v1/.well-known/jwks.json")
            signing_key = await asyncio.to_thread(client.get_signing_key_from_jwt, token)
            if signing_key.algorithm_name != algorithm:
                raise UnauthorizedError("Invalid authentication signing algorithm")
            key = signing_key.key
        else:
            raise UnauthorizedError("Unsupported authentication signing algorithm")
        payload = jwt.decode(
            token,
            key,
            algorithms=[algorithm],
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
    except jwt.PyJWKClientConnectionError:
        raise ServiceUnavailableError("Authentication key service is unavailable.") from None
    except jwt.PyJWKClientError:
        raise UnauthorizedError("Invalid authentication signing key") from None
    except jwt.InvalidTokenError:
        raise UnauthorizedError("Invalid authentication token") from None
    except ValueError:
        raise UnauthorizedError("Token 'sub' claim is not a valid UUID") from None


async def require_write_user(
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> UUID:
    """Database-shared fixed-window limit on authenticated mutations, across API replicas."""
    from backend.app.services.jobs.limits import consume_write
    await consume_write(db, user_id, settings.WRITE_REQUESTS_PER_HOUR)
    return user_id


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
