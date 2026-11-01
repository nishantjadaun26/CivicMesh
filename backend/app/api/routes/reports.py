"""Report creation, owner retrieval, and clarification answer endpoints."""

from typing import Annotated
from uuid import UUID

from backend.app.api.dependencies.auth import (
    get_current_user_id,
    require_report_owner,
    require_write_user,
)
from backend.app.core.errors import ConflictError
from backend.app.database.models import Evidence, Job, Report
from backend.app.database.session import get_db
from backend.app.schemas.reports import (
    ClarificationAnswerRequest,
    ReportCreateRequest,
    ReportResponse,
)
from backend.app.services.jobs.queue import JobQueueService
from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.post(
    "",
    response_model=ReportResponse,
    status_code=201,
    summary="Submit a new citizen report",
    description="Persists a report, binds verified media evidence, and enqueues an asynchronous AI processing job.",
)
async def create_report(
    request: ReportCreateRequest,
    user_id: Annotated[UUID, Depends(require_write_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key", max_length=128)] = None,
) -> ReportResponse:
    """Submit a genuine citizen report and enqueue background AI processing."""
    report, job = await JobQueueService.create_report_with_job(
        owner_id=user_id,
        request=request,
        idempotency_key=idempotency_key,
        db=db,
    )

    evidence_query = select(Evidence.id).where(Evidence.report_id == report.id)
    ev_res = await db.execute(evidence_query)
    evidence_ids = list(ev_res.scalars().all())

    return ReportResponse(
        id=report.id,
        owner_id=report.owner_id,
        category=report.category,
        text=report.text,
        latitude=report.latitude,
        longitude=report.longitude,
        location_confirmed=report.location_confirmed,
        evidence_ids=evidence_ids,
        status=report.status,
        job_id=job.id,
        extraction_result=report.extraction_result,
        created_at=report.created_at,
        updated_at=report.updated_at,
    )


@router.get(
    "/{report_id}",
    response_model=ReportResponse,
    summary="Retrieve an owner-authorized report and its extraction result",
)
async def get_report(
    report: Annotated[Report, Depends(require_report_owner)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ReportResponse:
    """Read a private citizen report. Cross-owner access is strictly forbidden."""
    evidence_query = select(Evidence.id).where(Evidence.report_id == report.id)
    ev_res = await db.execute(evidence_query)
    evidence_ids = list(ev_res.scalars().all())

    job_query = select(Job.id).where(Job.report_id == report.id).order_by(Job.created_at.desc()).limit(1)
    job_res = await db.execute(job_query)
    job_id = job_res.scalar_one_or_none()

    return ReportResponse(
        id=report.id,
        owner_id=report.owner_id,
        category=report.category,
        text=report.text,
        latitude=report.latitude,
        longitude=report.longitude,
        location_confirmed=report.location_confirmed,
        evidence_ids=evidence_ids,
        status=report.status,
        job_id=job_id,
        extraction_result=report.extraction_result,
        created_at=report.created_at,
        updated_at=report.updated_at,
    )


@router.post(
    "/{report_id}/answers",
    response_model=ReportResponse,
    summary="Submit clarification answers for a paused report",
)
async def submit_clarification_answers(
    report: Annotated[Report, Depends(require_report_owner)],
    request: ClarificationAnswerRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: Annotated[UUID, Depends(require_write_user)],
) -> ReportResponse:
    """Submit citizen clarification answers and re-enqueue processing to resume workflow."""
    from backend.app.services.jobs.answers import enqueue_answer
    job = (await db.execute(select(Job).where(Job.report_id == report.id))).scalar_one_or_none()
    if job is None or (job.pending_action or {}).get("kind") != "clarification":
        raise ConflictError("Report is not waiting for clarification input.")
    await enqueue_answer(db, job.id, report.owner_id, request.checkpoint_id, request.interrupt_id,
                         request.model_dump(mode="json", exclude={"checkpoint_id", "interrupt_id"}))
    await db.refresh(report)

    evidence_query = select(Evidence.id).where(Evidence.report_id == report.id)
    ev_res = await db.execute(evidence_query)
    evidence_ids = list(ev_res.scalars().all())

    return ReportResponse(
        id=report.id,
        owner_id=report.owner_id,
        category=report.category,
        text=report.text,
        latitude=report.latitude,
        longitude=report.longitude,
        location_confirmed=report.location_confirmed,
        evidence_ids=evidence_ids,
        status=report.status,
        job_id=job.id if job else None,
        extraction_result=report.extraction_result,
        created_at=report.created_at,
        updated_at=report.updated_at,
    )


@router.get("", response_model=list[ReportResponse], summary="List the authenticated citizen's private reports")
async def list_reports(
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
):
    reports = (await db.execute(select(Report).where(Report.owner_id == user_id)
                               .order_by(Report.created_at.desc(), Report.id)
                               .offset((page - 1) * limit).limit(limit))).scalars().all()
    return [await get_report(report, db) for report in reports]
