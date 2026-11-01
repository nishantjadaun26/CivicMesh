"""Job status inspection endpoint."""

from typing import Annotated

from backend.app.api.dependencies.auth import require_job_owner
from backend.app.database.models import Job
from backend.app.schemas.jobs import JobResponse, PendingAction
from fastapi import APIRouter, Depends

router = APIRouter(prefix="/jobs", tags=["Jobs"])


@router.get(
    "/{job_id}",
    response_model=JobResponse,
    summary="Retrieve authorized processing job status",
    description="Inspects background AI processing status and retrieves clarification requests if pending input.",
)
async def get_job_status(
    job: Annotated[Job, Depends(require_job_owner)],
) -> JobResponse:
    """Read processing job status. Cross-owner access is forbidden."""
    action = None
    if job.pending_action and isinstance(job.pending_action, dict):
        action = PendingAction(
            interrupt_id=job.pending_action.get("interrupt_id", ""),
            kind=job.pending_action.get("kind", ""),
            prompt=job.pending_action.get("prompt", {}),
        )

    return JobResponse(
        job_id=job.id,
        report_id=job.report_id,
        status=job.status,  # type: ignore
        attempts=job.attempts,
        max_attempts=job.max_attempts,
        error_code=job.error_code,
        error_message=job.error_message,
        checkpoint_id=job.checkpoint_id,
        pending_action=action,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )
