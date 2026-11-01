"""Job status inspection endpoint."""

from typing import Annotated
from uuid import UUID

from backend.app.api.dependencies.auth import require_job_owner, require_write_user
from backend.app.database.models import FollowUp, Job, Report
from backend.app.database.session import get_db
from backend.app.schemas.jobs import JobAnswerRequest, JobResponse, PendingAction
from backend.app.services.jobs.answers import enqueue_answer
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/jobs", tags=["Jobs"])


@router.get(
    "/{job_id}",
    response_model=JobResponse,
    summary="Retrieve authorized processing job status",
    description="Inspects background AI processing status and retrieves clarification requests if pending input.",
)
async def get_job_status(
    job: Annotated[Job, Depends(require_job_owner)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JobResponse:
    """Read processing job status. Cross-owner access is forbidden."""
    action = None
    if job.status == "waiting_for_input" and job.pending_action and isinstance(job.pending_action, dict):
        action = PendingAction(
            interrupt_id=job.pending_action.get("interrupt_id", ""),
            kind=job.pending_action.get("kind", ""),
            prompt=job.pending_action.get("prompt", {}),
        )

    target = await db.get(Report, job.report_id) if job.report_id else await db.get(FollowUp, job.follow_up_id)
    result = target.extraction_result if job.report_id else target.result
    return JobResponse(
        job_id=job.id,
        report_id=job.report_id,
        follow_up_id=job.follow_up_id,
        status=job.status,  # type: ignore
        attempts=job.attempts,
        failures=job.failures,
        max_attempts=job.max_attempts,
        error_code=job.error_code,
        error_message=job.error_message,
        checkpoint_id=job.checkpoint_id,
        pending_action=action,
        result=result if job.status == "completed" else None,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


@router.post("/{job_id}/answers", response_model=JobResponse, summary="Answer clarification or review a private workflow")
async def answer_job(
    request: JobAnswerRequest,
    job: Annotated[Job, Depends(require_job_owner)],
    user_id: Annotated[UUID, Depends(require_write_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    queued = await enqueue_answer(db, job.id, user_id, request.checkpoint_id,
                                  request.interrupt_id, request.reply.model_dump(mode="json"))
    return await get_job_status(queued, db)
