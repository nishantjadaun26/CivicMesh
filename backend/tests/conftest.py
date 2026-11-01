"""Test fixtures and test client configuration."""

import time
from collections.abc import AsyncGenerator
from uuid import UUID

import jwt
import pytest_asyncio
from backend.app.core.config import Settings, get_settings
from backend.app.database.models import Base
from backend.app.database.session import get_db
from backend.app.main import app
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Test database using aiosqlite in memory
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
)

TestingSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


def get_test_settings() -> Settings:
    return Settings(
        ENVIRONMENT="test",
        SUPABASE_JWT_SECRET="test-jwt-secret-key-32-chars-minimum-length!",
        DATABASE_URL=TEST_DATABASE_URL,
    )


def create_test_token(user_id: UUID, expired: bool = False) -> str:
    """Generate a signed test JWT for Supabase Auth simulation."""
    settings = get_test_settings()
    exp = int(time.time()) + (-3600 if expired else 3600)
    payload = {
        "sub": str(user_id),
        "aud": "authenticated",
        "role": "authenticated",
        "iss": f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1",
        "exp": exp,
    }
    return jwt.encode(payload, settings.SUPABASE_JWT_SECRET, algorithm="HS256")


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a clean isolated in-memory database for each test."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestingSessionLocal() as session:
        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession, monkeypatch) -> AsyncGenerator[AsyncClient, None]:
    """Test HTTP client with overridden DB dependency."""
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = get_test_settings

    # Isolated Storage transport: no real account, production calls or application fallback.
    import httpx
    from backend.app.database.models import Evidence
    from backend.app.services.storage import media
    from sqlalchemy import select
    native = httpx.AsyncClient
    monkeypatch.setattr(media, "settings", get_test_settings().model_copy(update={
        "SUPABASE_SERVICE_ROLE_KEY": "isolated-storage-key-with-no-real-account-access"}))
    async def handle_storage(request):
        if request.method == "POST":
            return httpx.Response(200, json={"url": request.url.path + "?token=isolated-test-ticket"})
        path = request.url.path.split("/civicmesh-evidence/", 1)[-1]
        evidence = (await db_session.execute(select(Evidence).where(Evidence.storage_path == path))).scalar_one_or_none()
        if evidence is None:
            return httpx.Response(404)
        headers = {"image/jpeg": b"\xff\xd8\xff", "image/png": b"\x89PNG\r\n\x1a\n"}
        content = headers.get(evidence.mime_type, b"ID3").ljust(evidence.file_size_bytes, b"x")
        return httpx.Response(200, content=content, headers={"content-type": evidence.mime_type})
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: native(transport=httpx.MockTransport(handle_storage), **kwargs))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c

    app.dependency_overrides.clear()
