from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query

from app.core.config import Settings, get_settings
from app.core.errors import pending, unavailable
from app.core.security import current_user
from app.schemas.contracts import (
    Answers,
    FollowUp,
    Health,
    Incident,
    IncidentPage,
    Job,
    JobAccepted,
    Report,
    ReportCreate,
    Submission,
    UploadPrepare,
    UploadPrepared,
)

router = APIRouter()
User = Annotated[UUID, Depends(current_user)]
Config = Annotated[Settings, Depends(get_settings)]
Idempotency = Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=128)]


def storage_boundary(settings: Settings, operation: str):
    if not settings.database_url:
        unavailable("Database")
    pending(operation)


@router.get("/health", response_model=Health)
def health(settings: Config):
    return Health(
        live=True,
        ready=False,
        services={
            "database": "configured_unverified" if settings.database_url else "not_configured",
            "auth": "configured_unverified"
            if settings.supabase_url and settings.supabase_publishable_key
            else "not_configured",
            "ai": "configured_unverified"
            if settings.gemini_api_key and settings.gemini_model
            else "not_configured",
            "jobs": "not_implemented",
            "checkpoint_store": "not_implemented",
        },
    )


@router.post("/uploads/prepare", response_model=UploadPrepared)
def prepare_upload(body: UploadPrepare, user: User, settings: Config):
    if not settings.supabase_service_role_key:
        unavailable("Private storage")
    pending("Authenticated upload preparation")


@router.post("/reports", response_model=Submission, status_code=202)
def create_report(body: ReportCreate, user: User, settings: Config, key: Idempotency):
    storage_boundary(settings, "Report submission")


@router.get("/reports/{report_id}", response_model=Report)
def get_report(report_id: UUID, user: User, settings: Config):
    storage_boundary(settings, "Owner-authorized report retrieval")


@router.post("/reports/{report_id}/answers", response_model=JobAccepted, status_code=202)
def answer_report(report_id: UUID, body: Answers, user: User, settings: Config, key: Idempotency):
    storage_boundary(settings, "Workflow resumption")


@router.get("/jobs/{job_id}", response_model=Job)
def get_job(job_id: UUID, user: User, settings: Config):
    storage_boundary(settings, "Owner-authorized job retrieval")


@router.get("/incidents", response_model=IncidentPage)
def list_incidents(
    settings: Config,
    limit: int = Query(20, ge=1, le=100),
    cursor: str | None = Query(None, max_length=256),
):
    storage_boundary(settings, "Approved public incident listing")


@router.get("/incidents/{incident_id}", response_model=Incident)
def get_incident(incident_id: UUID, settings: Config):
    storage_boundary(settings, "Approved public incident retrieval")


@router.post("/incidents/{incident_id}/follow-ups", response_model=JobAccepted, status_code=202)
def follow_up(incident_id: UUID, body: FollowUp, user: User, settings: Config, key: Idempotency):
    storage_boundary(settings, "Follow-up submission")
