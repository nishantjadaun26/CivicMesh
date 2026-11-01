"""Schemas for reports and clarification workflows."""

from datetime import datetime
from typing import Any
from uuid import UUID

from backend.app.schemas.common import (
    BaseSchema,
    Category,
    ConfirmedLocation,
    OptionalReportText,
)
from civicmesh_ai.integration import ReportCompletion
from pydantic import Field, model_validator


class ReportCreateRequest(BaseSchema):
    """Citizen input for creating a report."""
    text: OptionalReportText = ""
    public_summary: str = Field(default="", max_length=2500)
    share_on_map: bool = Field(default=False, strict=True)
    evidence_ids: list[UUID] = Field(default_factory=list, max_length=10)
    category: Category | None = None
    location: ConfirmedLocation | None = None

    @model_validator(mode="after")
    def validate_content_and_uniqueness(self):
        if not self.text and not self.evidence_ids:
            raise ValueError("Report must contain either a description or at least one piece of evidence.")
        if len(self.evidence_ids) != len(set(self.evidence_ids)):
            raise ValueError("Duplicate evidence identifiers are not allowed.")
        if self.share_on_map and (self.category is None or self.location is None):
            raise ValueError("A public map report requires a category and confirmed location.")
        return self


class ClarificationAnswerRequest(BaseSchema):
    """Citizen answer to a workflow clarification request."""
    checkpoint_id: str = Field(min_length=1)
    interrupt_id: str = Field(min_length=1)
    text: str = Field(default="", max_length=4000)
    category: Category | None = None
    location: ConfirmedLocation | None = None

    @model_validator(mode="after")
    def validate_has_answer(self):
        if not self.text and self.category is None and self.location is None:
            raise ValueError("Please provide an answer via text, category, or confirmed location.")
        return self


class ReportResponse(BaseSchema):
    """Authenticated citizen report response."""
    id: UUID
    owner_id: UUID
    category: Category | None
    text: str
    latitude: float | None
    longitude: float | None
    location_confirmed: bool = False
    evidence_ids: list[UUID]
    status: str
    job_id: UUID | None
    public_incident_id: UUID | None = None
    extraction_result: ReportCompletion | None = None
    created_at: datetime
    updated_at: datetime


class ReportDetailResponse(ReportResponse):
    """Detailed report with timeline events."""
    timeline: list[dict[str, Any]] = Field(default_factory=list)
