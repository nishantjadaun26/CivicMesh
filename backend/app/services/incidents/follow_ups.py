"""Persist private follow-up evidence and a real assessment job atomically."""

from uuid import uuid4

from backend.app.core.config import get_settings
from backend.app.core.errors import ConflictError, NotFoundError
from backend.app.database.models import Evidence, FollowUp, Incident, Job
from backend.app.services.storage.media import StorageService
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError


async def create_follow_up(db, incident_id, owner_id, request, key):
    incident = await db.get(Incident, incident_id)
    if incident is None or not incident.is_public:
        raise NotFoundError("Public incident not found")

    async def replay():
        existing = (await db.execute(select(FollowUp).where(FollowUp.owner_id == owner_id,
                                    FollowUp.idempotency_key == key))).scalar_one()
        ids = set((await db.execute(select(Evidence.id).where(Evidence.follow_up_id == existing.id))).scalars())
        if (existing.incident_id != incident_id or existing.text != request.text
                or existing.same_location_confirmed != request.same_location_confirmed
                or ids != set(request.evidence_ids)):
            raise ConflictError("Idempotency key already belongs to a different follow-up.")
        job = (await db.execute(select(Job).where(Job.follow_up_id == existing.id))).scalar_one()
        return existing, job

    if key:
        existing = (await db.execute(select(FollowUp.id).where(FollowUp.owner_id == owner_id,
                                    FollowUp.idempotency_key == key))).scalar_one_or_none()
        if existing:
            return await replay()
    follow_up = FollowUp(id=uuid4(), owner_id=owner_id, incident_id=incident_id,
                         text=request.text, same_location_confirmed=request.same_location_confirmed,
                         idempotency_key=key, status="pending")
    try:
        async with db.begin_nested():
            db.add(follow_up)
            await db.flush()
    except IntegrityError:
        if key:
            return await replay()
        raise
    await StorageService.verify_and_bind_evidence(
        owner_id=owner_id, evidence_ids=request.evidence_ids, db=db,
        incident_id=incident_id, follow_up_id=follow_up.id,
    )
    job = Job(id=uuid4(), owner_id=owner_id, follow_up_id=follow_up.id, kind="follow_up",
              status="pending", max_attempts=get_settings().WORKER_MAX_RETRIES)
    db.add(job)
    await db.commit()
    return follow_up, job
