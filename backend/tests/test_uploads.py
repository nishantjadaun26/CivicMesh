"""Tests for private media upload preparation and validation."""

from uuid import uuid4

import pytest
from backend.tests.conftest import create_test_token
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_prepare_upload_valid_image(client: AsyncClient):
    user_id = uuid4()
    token = create_test_token(user_id)

    response = await client.post(
        "/uploads/prepare",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "filename": "garbage_heap.jpg",
            "content_type": "image/jpeg",
            "file_size_bytes": 1024 * 500,  # 500 KB
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "evidence_id" in data
    assert "upload_url" in data
    assert "storage_path" in data
    assert str(user_id) in data["storage_path"]


@pytest.mark.asyncio
async def test_prepare_upload_invalid_mime_type(client: AsyncClient):
    user_id = uuid4()
    token = create_test_token(user_id)

    response = await client.post(
        "/uploads/prepare",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "filename": "malicious.exe",
            "content_type": "application/x-msdownload",
            "file_size_bytes": 1024,
        },
    )
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


@pytest.mark.asyncio
async def test_prepare_upload_oversized_image(client: AsyncClient):
    user_id = uuid4()
    token = create_test_token(user_id)

    response = await client.post(
        "/uploads/prepare",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "filename": "huge.png",
            "content_type": "image/png",
            "file_size_bytes": 20 * 1024 * 1024,  # 20 MB (> 15MB limit)
        },
    )
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
