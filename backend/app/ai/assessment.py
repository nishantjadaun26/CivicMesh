"""Typed priority, routing, complaint and follow-up contracts for backend integration."""

from typing import Literal
from uuid import UUID

from civicmesh_ai.schemas import Category, Extraction, OptionalReportText, Schema, ShortText
from pydantic import AwareDatetime, Field, HttpUrl, model_validator


class PriorityAssessment(Schema):
    """Advisory triage, not a verified emergency or official authority priority."""

    level: Literal["unknown", "low", "medium", "high"]
    rationale: ShortText
    supporting_observations: list[ShortText] = Field(default_factory=list, max_length=10)
    uncertainties: list[ShortText] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def require_support(self):
        """A known priority requires reported observations supporting the assessment."""
        if self.level != "unknown" and not self.supporting_observations:
            raise ValueError("Priority needs supporting observations")
        return self


class IncidentCandidate(Schema):
    """Backend-filtered candidate; AI does not merge reports or decide membership."""

    incident_id: UUID
    category: Category
    reason: ShortText
    distance_meters: float | None = Field(default=None, ge=0, allow_inf_nan=False)


class OfficialSource(Schema):
    """A backend-verified source passage, with immutable provenance metadata."""

    document_id: UUID
    authority_id: UUID
    authority_name: ShortText
    jurisdiction: ShortText
    url: HttpUrl
    retrieved_at: AwareDatetime
    verified_at: AwareDatetime
    supporting_passage: ShortText


class AuthorityRecommendation(Schema):
    """A recommendation must cite only supplied, backend-verified source passages."""

    authority_id: UUID | None = None
    source_ids: list[UUID] = Field(default_factory=list, max_length=10)
    rationale: ShortText
    uncertainties: list[ShortText] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def require_sources(self):
        """Unknown routing has no citations; a positive recommendation needs sources."""
        if (self.authority_id is None) != (not self.source_ids):
            raise ValueError("Authority and supporting sources must be supplied together")
        if len(set(self.source_ids)) != len(self.source_ids):
            raise ValueError("Duplicate source identifiers")
        return self


class ComplaintContent(Schema):
    """Model-authored draft content; trusted recipient and evidence are attached by code."""

    subject: ShortText
    observations: list[ShortText] = Field(min_length=1, max_length=10)
    requested_action: ShortText
    source_ids: list[UUID] = Field(min_length=1, max_length=10)
    limitations: list[ShortText] = Field(default_factory=list, max_length=10)


class FollowUpInput(Schema):
    """Owner-authorized baseline/follow-up references supplied by the backend."""

    incident_id: UUID
    baseline: Extraction
    baseline_evidence_ids: list[UUID] = Field(default_factory=list, max_length=5)
    follow_up_evidence_ids: list[UUID] = Field(default_factory=list, max_length=5)
    text: OptionalReportText = ""
    observed_at: AwareDatetime
    same_location_confirmed: bool = Field(strict=True)

    @model_validator(mode="after")
    def require_distinct_evidence(self):
        """Prevent the same attachment from serving as both before and after evidence."""
        ids = self.baseline_evidence_ids + self.follow_up_evidence_ids
        if len(ids) != len(set(ids)):
            raise ValueError("Baseline and follow-up evidence must be distinct")
        return self


class FollowUpAssessment(Schema):
    """An attributed AI observation, never an official resolution update."""

    outcome: Literal["appears_resolved", "partly_resolved", "persists", "insufficient_evidence"]
    rationale: ShortText
    evidence_ids: list[UUID] = Field(default_factory=list, max_length=10)
    limitations: list[ShortText] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def require_evidence(self):
        """Any condition stronger than unknown requires referenced evidence."""
        if self.outcome != "insufficient_evidence" and not self.evidence_ids:
            raise ValueError("A condition assessment requires evidence")
        if len(set(self.evidence_ids)) != len(self.evidence_ids):
            raise ValueError("Duplicate evidence identifiers")
        return self
