"""Reject invalid evidence contexts and oversized batches before Storage reads."""

from unittest.mock import AsyncMock
from uuid import UUID, uuid4

from backend.app.database.models import Evidence, Incident
from backend.app.services.storage.media import StorageService
from backend.tests.conftest import create_test_token


async def ticket(client, headers, size):
    response = await client.post(
        "/uploads/prepare",
        headers=headers,
        json={
            "filename": "isolated.jpg",
            "content_type": "image/jpeg",
            "file_size_bytes": size,
        },
    )
    assert response.status_code == 200
    return response.json()["evidence_id"]


async def test_oversized_batch_is_rejected_before_downloading_any_object(client, monkeypatch):
    headers = {"Authorization": f"Bearer {create_test_token(uuid4())}"}
    ids = [await ticket(client, headers, 7 * 1024 * 1024) for _ in range(2)]
    reader = AsyncMock(side_effect=AssertionError("Oversized batches must not download evidence"))
    monkeypatch.setattr(StorageService, "verify_uploaded_object", reader)
    response = await client.post("/reports", headers=headers, json={"evidence_ids": ids})
    assert response.status_code == 422
    assert "12 MiB" in response.json()["message"]
    reader.assert_not_awaited()


async def test_follow_up_evidence_cannot_be_rebound_as_report_evidence(
    client, db_session, monkeypatch
):
    owner = uuid4()
    headers = {"Authorization": f"Bearer {create_test_token(owner)}"}
    incident_id = uuid4()
    db_session.add(
        Incident(
            id=incident_id,
            category="garbage",
            latitude=1,
            longitude=2,
            observed_condition="Isolated baseline",
            is_public=True,
            authority_status="unknown",
        )
    )
    await db_session.commit()
    evidence_id = await ticket(client, headers, 100)
    submitted = await client.post(
        f"/incidents/{incident_id}/follow-ups",
        headers=headers,
        json={"evidence_ids": [evidence_id], "same_location_confirmed": True},
    )
    assert submitted.status_code == 201
    reader = AsyncMock(side_effect=AssertionError("Bound follow-up evidence must not be read"))
    monkeypatch.setattr(StorageService, "verify_uploaded_object", reader)
    response = await client.post("/reports", headers=headers, json={"evidence_ids": [evidence_id]})
    assert response.status_code == 422
    reader.assert_not_awaited()
    await db_session.rollback()
    evidence = await db_session.get(Evidence, UUID(evidence_id))
    assert evidence.report_id is None and str(evidence.follow_up_id) == submitted.json()["id"]
