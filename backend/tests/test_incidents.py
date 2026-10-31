"""Tests for approved public incidents and follow-up submissions."""

from uuid import uuid4

import pytest
from backend.app.database.models import Incident
from backend.tests.conftest import create_test_token
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_list_and_detail_public_incidents(client: AsyncClient, db_session: AsyncSession):
    # Public incident
    inc_pub = Incident(
        id=uuid4(),
        category="water_leak",
        latitude=28.6139,
        longitude=77.2090,
        observed_condition="Pipe burst leaking clean water onto pavement",
        authority_status="unknown",  # Official status remains unknown
        is_public=True,
    )
    # Private / unapproved incident
    inc_priv = Incident(
        id=uuid4(),
        category="garbage",
        latitude=28.6150,
        longitude=77.2090,
        observed_condition="Unreviewed report",
        authority_status="unknown",
        is_public=False,
    )
    db_session.add_all([inc_pub, inc_priv])
    await db_session.commit()

    # List endpoint returns only public incident
    res = await client.get("/incidents")
    assert res.status_code == 200
    items = res.json()
    assert len(items) == 1
    assert items[0]["id"] == str(inc_pub.id)
    assert items[0]["observed_condition"] == "Pipe burst leaking clean water onto pavement"
    assert items[0]["authority_status"] == "unknown"

    # Detail endpoint
    detail_res = await client.get(f"/incidents/{inc_pub.id}")
    assert detail_res.status_code == 200
    assert detail_res.json()["id"] == str(inc_pub.id)

    # Private incident returns 404
    priv_res = await client.get(f"/incidents/{inc_priv.id}")
    assert priv_res.status_code == 404


@pytest.mark.asyncio
async def test_submit_follow_up(client: AsyncClient, db_session: AsyncSession):
    user_id = uuid4()
    token = create_test_token(user_id)

    inc = Incident(
        id=uuid4(),
        category="garbage",
        latitude=28.6139,
        longitude=77.2090,
        observed_condition="Initial garbage pile",
        authority_status="unknown",
        is_public=True,
    )
    db_session.add(inc)
    await db_session.commit()

    # First prepare an evidence item for follow-up
    upload_res = await client.post(
        "/uploads/prepare",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "filename": "follow_up.jpg",
            "content_type": "image/jpeg",
            "file_size_bytes": 1024 * 100,
        },
    )
    evidence_id = upload_res.json()["evidence_id"]

    # Submit follow-up
    fu_res = await client.post(
        f"/incidents/{inc.id}/follow-ups",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "text": "Garbage has been partly cleared by sanitation workers",
            "evidence_ids": [evidence_id],
            "same_location_confirmed": True,
        },
    )
    assert fu_res.status_code == 201
    assert fu_res.json()["incident_id"] == str(inc.id)

    # Check incident detail shows new observation in timeline without altering authority_status
    detail = await client.get(f"/incidents/{inc.id}")
    assert detail.status_code == 200
    d_json = detail.json()
    assert d_json["authority_status"] == "unknown"  # Authority status is preserved
    assert len(d_json["timeline"]) == 1
    assert d_json["timeline"][0]["event_type"] == "citizen_observation"
