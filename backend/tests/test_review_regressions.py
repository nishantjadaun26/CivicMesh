"""Regression tests for merge-review authentication, media and privacy findings."""
from unittest.mock import AsyncMock
from uuid import uuid4

import jwt
import pytest
from backend.app.core.config import Settings, get_settings
from backend.app.database.models import Evidence
from backend.app.main import app
from backend.app.services.storage import media
from backend.tests.conftest import create_test_token, get_test_settings
from httpx import AsyncClient
from pydantic import ValidationError
from sqlalchemy import func, select


@pytest.mark.parametrize("changes", [{"aud": "other-project"}, {"iss": "https://other.invalid/auth/v1"}, {"role": "service_role"}, {"exp": None}])
async def test_reject_invalid_token_claims(client, changes):
    payload = jwt.decode(create_test_token(uuid4()), options={"verify_signature": False})
    payload.update(changes)
    if payload.get("exp") is None:
        payload.pop("exp", None)
    token = jwt.encode(payload, get_test_settings().SUPABASE_JWT_SECRET, algorithm="HS256")
    response = await client.get(f"/jobs/{uuid4()}", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


async def test_placeholder_signing_secret_never_authenticates(client):
    app.dependency_overrides[get_settings] = lambda: Settings()
    token = jwt.encode({"sub": str(uuid4()), "aud": "authenticated"}, "dev-supabase-jwt-secret-placeholder", algorithm="HS256")
    response = await client.get(f"/jobs/{uuid4()}", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 503


async def test_failed_upload_signing_returns_no_ticket_or_record(client, db_session, monkeypatch):
    native = AsyncClient
    async def handle(request):
        return media.httpx.Response(503, text="secret provider error")
    monkeypatch.setattr(media.httpx, "AsyncClient", lambda **kwargs: native(transport=media.httpx.MockTransport(handle), **kwargs))
    response = await client.post("/uploads/prepare", headers={"Authorization": f"Bearer {create_test_token(uuid4())}"},
        json={"filename": "real.jpg", "content_type": "image/jpeg", "file_size_bytes": 100})
    assert response.status_code == 503
    assert "secret provider error" not in response.text
    assert (await db_session.execute(select(func.count()).select_from(Evidence))).scalar_one() == 0


async def test_health_never_exposes_database_exception(client, db_session, monkeypatch):
    monkeypatch.setattr(db_session, "execute", AsyncMock(side_effect=RuntimeError("postgres://private-password")))
    response = await client.get("/health")
    assert response.status_code == 503
    assert "private-password" not in response.text
    assert response.json()["request_id"] == response.headers["X-Request-ID"]


def test_cors_rejects_wildcards_and_non_origins():
    for origin in ["*", "https://*.example.com", "https://example.com/path"]:
        with pytest.raises(ValidationError):
            Settings(CORS_ORIGINS=[origin])


async def test_idempotency_key_cannot_replay_a_different_payload(client):
    token = create_test_token(uuid4())
    headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": "isolated-idempotency-key"}
    first = await client.post("/reports", headers=headers, json={"text": "Original observation"})
    assert first.status_code == 201
    second = await client.post("/reports", headers=headers, json={"text": "Different observation"})
    assert second.status_code == 409


async def test_unuploaded_evidence_cannot_be_bound(client, db_session, monkeypatch):
    user_id = uuid4()
    token = create_test_token(user_id)
    upload = await client.post("/uploads/prepare", headers={"Authorization": f"Bearer {token}"},
        json={"filename": "photo.jpg", "content_type": "image/jpeg", "file_size_bytes": 100})
    evidence_id = upload.json()["evidence_id"]
    async def missing(request):
        return media.httpx.Response(404)
    monkeypatch.setattr(media.httpx, "AsyncClient", lambda **kwargs: AsyncClient(transport=media.httpx.MockTransport(missing), **kwargs))
    response = await client.post("/reports", headers={"Authorization": f"Bearer {token}"},
        json={"evidence_ids": [evidence_id]})
    assert response.status_code == 422
