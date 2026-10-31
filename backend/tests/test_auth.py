"""HTTP transport doubles verify token handling; no mock application fallback exists."""

from uuid import UUID

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core import security
from app.core.config import Settings, get_settings
from app.main import create_app


@pytest.mark.parametrize(
    "status,payload,expected",
    [
        (401, {}, 401),
        (503, {}, 503),
        (200, {"id": "not-a-uuid"}, 503),
        (200, {"id": str(UUID(int=1))}, 501),
    ],
)
def test_supabase_verification(monkeypatch, status, payload, expected):
    original = httpx.AsyncClient

    def handle(request):
        assert request.url == "https://unit-test.supabase.co/auth/v1/user"
        assert request.headers["authorization"] == "Bearer isolated-test-token"
        return httpx.Response(status, json=payload)

    monkeypatch.setattr(
        security.httpx,
        "AsyncClient",
        lambda **kwargs: original(transport=httpx.MockTransport(handle), **kwargs),
    )
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None,
        supabase_url="https://unit-test.supabase.co",
        supabase_publishable_key="isolated-test-key",
        database_url="postgresql+psycopg://unused",
    )
    response = TestClient(app).get(
        "/jobs/00000000-0000-0000-0000-000000000001",
        headers={"Authorization": "Bearer isolated-test-token"},
    )
    assert response.status_code == expected
