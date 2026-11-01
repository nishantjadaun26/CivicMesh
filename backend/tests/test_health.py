"""Tests for health and readiness reporting."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check_healthy(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["details"]["environment"] == "test"
    assert data["details"]["database"] == "connected"


@pytest.mark.asyncio
async def test_request_id_header(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    assert "X-Request-ID" in response.headers
    assert response.headers["X-Request-ID"].startswith("req-")
