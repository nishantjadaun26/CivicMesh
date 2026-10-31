from uuid import UUID

import httpx
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import Settings, get_settings
from app.core.errors import ServiceError, unavailable

bearer = HTTPBearer(auto_error=False)


async def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    settings: Settings = Depends(get_settings),
) -> UUID:
    if not credentials or credentials.scheme.lower() != "bearer":
        raise ServiceError(401, "unauthenticated", "A valid access token is required.")
    if not settings.supabase_url or not settings.supabase_publishable_key:
        unavailable("Authentication")
    # Supabase Auth validates the token server-side, including expiry and signature.
    # Never decode an unverified JWT or trust a client-supplied user ID.
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=False) as client:
            response = await client.get(
                f"{settings.supabase_url}/auth/v1/user",
                headers={
                    "apikey": settings.supabase_publishable_key,
                    "Authorization": f"Bearer {credentials.credentials}",
                },
            )
        if response.status_code in (401, 403):
            raise ServiceError(401, "unauthenticated", "Access token is invalid or expired.")
        if response.status_code != 200:
            unavailable("Authentication provider")
        return UUID(response.json()["id"])
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        unavailable("Authentication provider")
