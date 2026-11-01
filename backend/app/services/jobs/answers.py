"""Queue one action-specific reply to an owner-authorized saved checkpoint."""

from backend.app.core.errors import ConflictError, ValidationError
from backend.app.database.models import FollowUp, Job, Report, utc_now
from civicmesh_ai.schemas import Clarification, ReviewDecision
from pydantic import ValidationError as SchemaError
from sqlalchemy import select


async def enqueue_answer(db, job_id, owner_id, checkpoint_id, interrupt_id, reply):
    job = (await db.execute(select(Job).where(Job.id == job_id, Job.owner_id == owner_id)
                            .with_for_update())).scalar_one_or_none()
    if job is None or job.status != "waiting_for_input":
        raise ConflictError("Job is not waiting for input.")
    action = job.pending_action or {}
    if job.checkpoint_id != checkpoint_id or action.get("interrupt_id") != interrupt_id:
        raise ConflictError("Workflow changed. Reload the current review before replying.")
    schema = Clarification if action.get("kind") == "clarification" else ReviewDecision
    try:
        validated = schema.model_validate(reply).model_dump(mode="json")
    except SchemaError:
        raise ValidationError("Reply does not match the current workflow action.") from None
    job.pending_action = {**action, "resume_pending": True, "reply": validated}
    job.status = "pending"
    job.available_at = utc_now()
    target = await db.get(Report, job.report_id) if job.report_id else await db.get(FollowUp, job.follow_up_id)
    target.status = "pending"
    await db.commit()
    return job
