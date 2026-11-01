"""Integration-boundary security and readiness regressions."""

from types import SimpleNamespace
from uuid import uuid4

import jwt
from backend.app.api.dependencies import auth
from backend.app.core.config import get_settings
from backend.app.database.models import WorkerHeartbeat, utc_now
from backend.app.main import app
from backend.tests.conftest import create_test_token, get_test_settings
from cryptography.hazmat.primitives.asymmetric import ec


async def test_asymmetric_jwks_token_is_scoped_to_project_and_citizen(client, monkeypatch):
    owner = uuid4()
    private = ec.generate_private_key(ec.SECP256R1())
    jwk = jwt.PyJWK.from_json(jwt.algorithms.ECAlgorithm.to_jwk(private.public_key()), algorithm="ES256")
    seen = []
    def project(url):
        seen.append(url)
        return SimpleNamespace(get_signing_key_from_jwt=lambda token: jwk)
    monkeypatch.setattr(auth, "project_jwks", project)
    claims = jwt.decode(create_test_token(owner), options={"verify_signature": False})
    token = jwt.encode(claims, private, algorithm="ES256", headers={"kid": "isolated-test-key"})
    response = await client.get("/reports", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert seen == [get_test_settings().SUPABASE_URL + "/auth/v1/.well-known/jwks.json"]
    claims["iss"] = "https://another-project.invalid/auth/v1"
    wrong = jwt.encode(claims, private, algorithm="ES256", headers={"kid": "isolated-test-key"})
    assert (await client.get("/reports", headers={"Authorization": f"Bearer {wrong}"})).status_code == 401


async def test_write_limits_are_shared_in_database_and_reads_remain_available(client):
    app.dependency_overrides[get_settings] = lambda: get_test_settings().model_copy(update={"WRITE_REQUESTS_PER_HOUR": 1})
    headers = {"Authorization": f"Bearer {create_test_token(uuid4())}"}
    assert (await client.post("/reports", headers=headers, json={"text": "Isolated first report"})).status_code == 201
    assert (await client.post("/reports", headers=headers, json={"text": "Isolated second report"})).status_code == 429
    response = await client.get("/reports", headers=headers)
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"


async def test_readiness_requires_recent_initialized_worker(client, db_session):
    assert (await client.get("/health/live")).status_code == 200
    assert (await client.get("/health/ready")).status_code == 503
    db_session.add(WorkerHeartbeat(worker_id="isolated-worker", last_seen=utc_now()))
    await db_session.commit()
    response = await client.get("/health/ready")
    assert response.status_code == 200 and response.json()["ready"] is True


async def test_large_json_request_is_rejected_before_processing(client):
    response = await client.post("/reports", content=b"x" * 65537)
    assert response.status_code == 413
    assert response.json()["request_id"] == response.headers["X-Request-ID"]
