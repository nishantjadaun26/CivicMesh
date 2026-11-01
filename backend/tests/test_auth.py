"""Tests for Supabase JWT verification and cross-owner access isolation."""

from uuid import uuid4

import pytest
from backend.tests.conftest import create_test_token
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_missing_auth_header(client: AsyncClient):
    response = await client.post("/uploads/prepare", json={
        "filename": "test.jpg",
        "content_type": "image/jpeg",
        "file_size_bytes": 1024,
    })
    assert response.status_code == 401
    assert response.json()["code"] == "unauthorized"


@pytest.mark.asyncio
async def test_expired_token(client: AsyncClient):
    user_id = uuid4()
    expired_token = create_test_token(user_id, expired=True)
    response = await client.post(
        "/uploads/prepare",
        headers={"Authorization": f"Bearer {expired_token}"},
        json={
            "filename": "test.jpg",
            "content_type": "image/jpeg",
            "file_size_bytes": 1024,
        },
    )
    assert response.status_code == 401
    assert "expired" in response.json()["message"].lower()


@pytest.mark.asyncio
async def test_tampered_token(client: AsyncClient):
    response = await client.post(
        "/uploads/prepare",
        headers={"Authorization": "Bearer not-a-valid-jwt.token.here"},
        json={
            "filename": "test.jpg",
            "content_type": "image/jpeg",
            "file_size_bytes": 1024,
        },
    )
    assert response.status_code == 401
    assert response.json()["code"] == "unauthorized"


@pytest.mark.asyncio
async def test_cross_owner_isolation(client: AsyncClient):
    """User B must not be able to read or modify User A's private report or job."""
    user_a = uuid4()
    user_b = uuid4()
    token_a = create_test_token(user_a)
    token_b = create_test_token(user_b)

    # User A creates a report
    create_res = await client.post(
        "/reports",
        headers={"Authorization": f"Bearer {token_a}"},
        json={
            "text": "Garbage pile near the park entrance",
            "category": "garbage",
            "location": {
                "latitude": 28.6139,
                "longitude": 77.2090,
                "confirmed": True,
            },
        },
    )
    assert create_res.status_code == 201
    report_data = create_res.json()
    report_id = report_data["id"]
    job_id = report_data["job_id"]

    # User A can read their own report and job
    read_a = await client.get(f"/reports/{report_id}", headers={"Authorization": f"Bearer {token_a}"})
    assert read_a.status_code == 200

    job_a = await client.get(f"/jobs/{job_id}", headers={"Authorization": f"Bearer {token_a}"})
    assert job_a.status_code == 200

    # User B attempts to read User A's report -> 403 Forbidden
    read_b = await client.get(f"/reports/{report_id}", headers={"Authorization": f"Bearer {token_b}"})
    assert read_b.status_code == 403
    assert read_b.json()["code"] == "forbidden"

    # User B attempts to inspect User A's job -> 403 Forbidden
    job_b = await client.get(f"/jobs/{job_id}", headers={"Authorization": f"Bearer {token_b}"})
    assert job_b.status_code == 403
    assert job_b.json()["code"] == "forbidden"
