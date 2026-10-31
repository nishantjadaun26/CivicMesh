"""Schemas for approved public incidents, timelines, and follow-ups."""

from datetime import datetime
from typing import Any
from uuid import UUID

from backend.app.schemas.common import BaseSchema, Category, OptionalReportText
from pydantic import Field, model_validator


class StatusEventResponse(BaseSchema):
    id: UUID
    event_type: str  # citizen_observation, ai_assessment, authority_update
    payload: dict[str, Any]
    created_at: datetime


class IncidentPublicResponse(BaseSchema):
    """Approved public incident projection. Omits private citizen details."""
    id: UUID
    category: Category
    latitude: float
    longitude: float
    observed_condition: str = Field(description="Citizen-observed condition or AI assessment")
    authority_status: str = Field(default="unknown", description="Verified official authority response only")
    is_public: bool = True
    created_at: datetime
    updated_at: datetime


class IncidentDetailResponse(IncidentPublicResponse):
    """Public incident detail with verified timeline events."""
    timeline: list[StatusEventResponse] = Field(default_factory=list)


class FollowUpCreateRequest(BaseSchema):
    """Citizen submission of follow-up observations and evidence."""
    text: OptionalReportText = ""
    evidence_ids: list[UUID] = Field(default_factory=list, min_length=1, max_length=5)
    same_location_confirmed: bool = Field(strict=True)

    @model_validator(mode="after")
    def validate_follow_up(self):
        if not self.same_location_confirmed:
            raise ValueError("Must confirm observation is at the same location as original incident.")
        if len(self.evidence_ids) != len(set(self.evidence_ids)):
            raise ValueError("Duplicate evidence identifiers are not allowed.")
        return self


class FollowUpResponse(BaseSchema):
    id: UUID
    incident_id: UUID
    status: str
    created_at: datetime
