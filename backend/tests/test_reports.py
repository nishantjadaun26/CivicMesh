"""Tests for report creation, idempotency, persistence, and clarification answers."""

from uuid import UUID, uuid4

import pytest
from backend.app.database.models import Job, Report
from backend.tests.conftest import create_test_token
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_create_and_retrieve_text_report(client: AsyncClient):
    """First Deliverable: Authenticated citizen creates report, reads it, and tracks job."""
    user_id = uuid4()
    token = create_test_token(user_id)

    # 1. Create text report
    payload = {
        "text": "Severe water leak on 5th Main Road corner",
        "category": "water_leak",
        "location": {
            "latitude": 28.6139,
            "longitude": 77.2090,
            "confirmed": True,
        },
    }
    response = await client.post(
        "/reports",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )
    assert response.status_code == 201
    data = response.json()

    assert data["owner_id"] == str(user_id)
    assert data["category"] == "water_leak"
    assert data["text"] == "Severe water leak on 5th Main Road corner"
    assert data["latitude"] == 28.6139
    assert data["longitude"] == 77.2090
    assert data["location_confirmed"] is True
    assert data["status"] == "pending"
    assert data["job_id"] is not None

    report_id = data["id"]
    job_id = data["job_id"]

    # 2. Retrieve own report
    fetch_res = await client.get(
        f"/reports/{report_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert fetch_res.status_code == 200
    fetch_data = fetch_res.json()
    assert fetch_data["id"] == report_id

    # 3. Track job
    job_res = await client.get(
        f"/jobs/{job_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert job_res.status_code == 200
    job_data = job_res.json()
    assert job_data["job_id"] == job_id
    assert job_data["status"] == "pending"
    assert job_data["attempts"] == 0


@pytest.mark.asyncio
async def test_report_submission_idempotency(client: AsyncClient):
    """Repeated submissions with the same Idempotency-Key return existing records without duplicates."""
    user_id = uuid4()
    token = create_test_token(user_id)
    idempotency_key = f"idem-key-{uuid4()}"

    payload = {
        "text": "Duplicate submission test",
        "category": "garbage",
    }

    # First attempt
    res1 = await client.post(
        "/reports",
        headers={
            "Authorization": f"Bearer {token}",
            "Idempotency-Key": idempotency_key,
        },
        json=payload,
    )
    assert res1.status_code == 201
    report1 = res1.json()

    # Second attempt with identical idempotency key
    res2 = await client.post(
        "/reports",
        headers={
            "Authorization": f"Bearer {token}",
            "Idempotency-Key": idempotency_key,
        },
        json=payload,
    )
    assert res2.status_code == 201
    report2 = res2.json()

    # Both must reference the exact same report ID and job ID
    assert report1["id"] == report2["id"]
    assert report1["job_id"] == report2["job_id"]


@pytest.mark.asyncio
async def test_report_validation_empty_submission(client: AsyncClient):
    """Report without text or evidence must be rejected with 422."""
    user_id = uuid4()
    token = create_test_token(user_id)

    response = await client.post(
        "/reports",
        headers={"Authorization": f"Bearer {token}"},
        json={"text": ""},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


@pytest.mark.asyncio
async def test_submit_clarification_answers(client: AsyncClient, db_session: AsyncSession):
    """Submitting clarification answers updates the report and re-enqueues the job."""
    user_id = uuid4()
    token = create_test_token(user_id)

    # Create initial report missing confirmed location (starts in pending)
    create_res = await client.post(
        "/reports",
        headers={"Authorization": f"Bearer {token}"},
        json={"text": "Water leaking near the bus stop"},
    )
    assert create_res.status_code == 201
    report_id = UUID(create_res.json()["id"])
    job_id = UUID(create_res.json()["job_id"])

    # 1. Submitting answer for a pending job must be rejected with 409 Conflict
    pending_attempt = await client.post(
        f"/reports/{report_id}/answers",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "checkpoint_id": "chk-12345",
            "interrupt_id": "intr-abcde",
            "text": "Opposite the bakery",
        },
    )
    assert pending_attempt.status_code == 409
    assert pending_attempt.json()["code"] == "conflict"

    # 2. Put report and job into waiting_for_input state with matching checkpoint
    report = await db_session.get(Report, report_id)
    assert report is not None
    report.status = "waiting_for_input"
    job = await db_session.get(Job, job_id)
    assert job is not None
    job.status = "waiting_for_input"
    job.checkpoint_id = "chk-12345"
    job.pending_action = {"interrupt_id": "intr-abcde", "kind": "clarification", "prompt": {}}
    await db_session.commit()

    # 3. Submitting with mismatched interrupt_id must fail with 409 Conflict
    bad_interrupt = await client.post(
        f"/reports/{report_id}/answers",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "checkpoint_id": "chk-12345",
            "interrupt_id": "wrong-interrupt",
            "text": "Opposite the bakery",
        },
    )
    assert bad_interrupt.status_code == 409

    # 4. Submit valid clarification answer with confirmed location
    clarify_res = await client.post(
        f"/reports/{report_id}/answers",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "checkpoint_id": "chk-12345",
            "interrupt_id": "intr-abcde",
            "text": "Opposite the blue bakery",
            "category": "water_leak",
            "location": {
                "latitude": 28.6140,
                "longitude": 77.2095,
                "confirmed": True,
            },
        },
    )
    assert clarify_res.status_code == 200
    updated = clarify_res.json()
    assert updated["category"] is None
    assert updated["latitude"] is None
    assert updated["location_confirmed"] is False
    assert updated["text"] == "Water leaking near the bus stop"
    await db_session.refresh(job)
    assert job.pending_action["reply"]["text"] == "Opposite the blue bakery"
    assert job.pending_action["resume_pending"] is True
    assert updated["status"] == "pending"
