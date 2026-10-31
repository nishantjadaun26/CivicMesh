from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

Category = Literal["garbage", "water_leak"]
Assessment = Literal["appears_resolved", "partly_resolved", "persists", "insufficient_evidence"]
JobState = Literal["queued", "running", "waiting_for_input", "succeeded", "failed", "cancelled"]
Mime = Literal[
    "image/jpeg",
    "image/png",
    "image/webp",
    "audio/webm",
    "audio/ogg",
    "audio/mp4",
    "audio/mpeg",
    "audio/wav",
]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ErrorResponse(Contract):
    code: str
    message: str
    request_id: str
    details: list[dict[str, str]] | None = None


class Health(Contract):
    live: bool
    ready: bool
    services: dict[str, str]


class Location(Contract):
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)
    confirmed: Literal[True]


class UploadPrepare(Contract):
    mime_type: Mime
    size_bytes: int = Field(gt=0, le=20 * 1024 * 1024)

    @model_validator(mode="after")
    def photo_limit(self):
        if self.mime_type.startswith("image/") and self.size_bytes > 10 * 1024 * 1024:
            raise ValueError("Images are limited to 10 MiB")
        return self


class UploadPrepared(Contract):
    evidence_id: UUID
    upload_url: str
    method: Literal["PUT"]
    headers: dict[str, str]
    expires_at: AwareDatetime


class ReportCreate(Contract):
    text: str = Field(default="", max_length=10000)
    category: Category
    location: Location
    evidence_ids: list[UUID] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def requires_content(self):
        if not self.text.strip() and not self.evidence_ids:
            raise ValueError("Text or uploaded evidence is required")
        return self


class Submission(Contract):
    report_id: UUID
    job_id: UUID


class Extraction(Contract):
    category: Category | None = None
    summary: str | None = None
    missing_information: list[str] = Field(default_factory=list)
    language: Literal["hi", "en"] | None = None


class Report(ReportCreate):
    report_id: UUID
    created_at: AwareDatetime
    extraction: Extraction | None = None


class Answers(Contract):
    answers: dict[str, str] = Field(max_length=20)


class Job(Contract):
    job_id: UUID
    status: JobState
    attempts: int = Field(ge=0)
    created_at: AwareDatetime
    updated_at: AwareDatetime
    error_code: str | None = None


class Incident(Contract):
    incident_id: UUID
    category: Category
    public_summary: str
    authority_status: Literal["unknown", "acknowledged", "in_progress", "resolved"]
    observed_condition: Assessment | None = None
    created_at: AwareDatetime
    # No private location, owner, raw report, or unapproved evidence in public DTOs.


class IncidentPage(Contract):
    items: list[Incident]
    next_cursor: str | None = None


class FollowUp(Contract):
    text: str = Field(min_length=1, max_length=10000)
    evidence_ids: list[UUID] = Field(default_factory=list, max_length=10)
    observed_at: AwareDatetime


class JobAccepted(Contract):
    job_id: UUID
