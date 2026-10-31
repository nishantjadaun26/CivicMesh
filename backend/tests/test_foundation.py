"""Isolated verification fixtures only; never loaded as application data."""

from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.core.security import current_user
from app.main import create_app
from app.schemas.contracts import Extraction, Location, ReportCreate, UploadPrepare


@pytest.fixture
def client():
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None)
    with TestClient(app) as client:
        yield client


def test_health_is_live_but_not_ready(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["live"] is True
    assert response.json()["ready"] is False


@pytest.mark.parametrize(
    "method,path",
    [
        ("post", "/uploads/prepare"),
        ("post", "/reports"),
        ("get", "/reports/00000000-0000-0000-0000-000000000001"),
        ("post", "/reports/00000000-0000-0000-0000-000000000001/answers"),
        ("get", "/jobs/00000000-0000-0000-0000-000000000001"),
        ("post", "/incidents/00000000-0000-0000-0000-000000000001/follow-ups"),
    ],
)
def test_private_operations_reject_unauthenticated(client, method, path):
    response = getattr(client, method)(path)
    assert response.status_code == 401
    assert response.json()["code"] == "unauthenticated"
    assert response.json()["request_id"] == response.headers["x-request-id"]


def test_unconfigured_auth_does_not_accept_fake_token(client):
    response = client.get(
        "/jobs/00000000-0000-0000-0000-000000000001",
        headers={"Authorization": "Bearer arbitrary-user-id"},
    )
    assert response.status_code == 503


def test_unconfigured_storage_and_explicit_pending(client):
    assert client.get("/incidents").status_code == 503
    client.app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None, database_url="postgresql+psycopg://unused"
    )
    response = client.get("/incidents")
    assert response.status_code == 501
    assert response.json()["code"] == "not_implemented"


def test_upload_limits_and_owner_cannot_be_supplied(client):
    client.app.dependency_overrides[current_user] = lambda: UUID(int=1)
    valid = {"mime_type": "image/jpeg", "size_bytes": 1024}
    assert client.post("/uploads/prepare", json=valid).status_code == 503
    assert (
        client.post("/uploads/prepare", json={**valid, "owner_id": str(UUID(int=2))}).status_code
        == 422
    )
    for body in [
        {"mime_type": "image/svg+xml", "size_bytes": 1},
        {"mime_type": "image/png", "size_bytes": 10 * 1024 * 1024 + 1},
        {"mime_type": "audio/webm", "size_bytes": 20 * 1024 * 1024 + 1},
    ]:
        with pytest.raises(ValidationError):
            UploadPrepare.model_validate(body)


def test_location_confirmation_and_unknown_extraction():
    for values in [
        dict(latitude=91, longitude=0, confirmed=True),
        dict(latitude=0, longitude=-181, confirmed=True),
        dict(latitude=0, longitude=0, confirmed=False),
        dict(latitude=float("nan"), longitude=0, confirmed=True),
    ]:
        with pytest.raises(ValidationError):
            Location(**values)
    with pytest.raises(ValidationError):
        ReportCreate(category="garbage", location=Location(latitude=0, longitude=0, confirmed=True))
    assert Extraction().category is None
    with pytest.raises(ValidationError):
        Extraction.model_validate_json('{"category":"invented"}')


def test_errors_do_not_echo_private_values(client):
    response = client.get("/incidents", params={"limit": "private-marker"})
    assert response.status_code == 422
    assert "private-marker" not in response.text
    assert {"code", "message", "request_id", "details"} == set(response.json())


def test_cors_configuration_rejects_wildcard():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, cors_origins=["*"])


def test_public_contract_has_no_private_fields():
    from app.schemas.contracts import Incident

    assert (
        not {"owner_id", "latitude", "longitude", "location", "evidence_ids"}
        & Incident.model_fields.keys()
    )
