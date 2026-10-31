"""Typed private results for the authenticated backend/worker integration boundary."""

from typing import Any, Literal
from uuid import UUID

from civicmesh_ai.assessment import (
    AuthorityRecommendation,
    ComplaintContent,
    FollowUpAssessment,
    IncidentCandidate,
    OfficialSource,
    PriorityAssessment,
)
from civicmesh_ai.schemas import ConfirmedLocation, ExtractionResult, Schema, ShortText
from pydantic import AwareDatetime, Field, model_validator

WorkflowKind = Literal["report", "follow_up"]
ActionKind = Literal["clarification", "extraction_review", "complaint_review", "follow_up_review"]


class ComplaintPacket(Schema):
    """A private unsubmitted draft assembled from validated observations and sources."""

    report_id: UUID
    authority_id: UUID
    authority_name: ShortText
    jurisdiction: ShortText
    location: ConfirmedLocation
    content: ComplaintContent
    sources: list[OfficialSource] = Field(min_length=1, max_length=10)
    evidence_ids: list[UUID] = Field(default_factory=list, max_length=10)
    authority_status: Literal["unknown"]
    submitted: Literal[False]

    @model_validator(mode="after")
    def bind_sources(self):
        """Ensure typed packets retain the exact cited provenance and one trusted recipient."""
        ids = [source.document_id for source in self.sources]
        if len(ids) != len(set(ids)) or set(ids) != set(self.content.source_ids):
            raise ValueError("Packet sources must match its citations exactly")
        if any(
            (source.authority_id, source.authority_name, source.jurisdiction)
            != (self.authority_id, self.authority_name, self.jurisdiction)
            for source in self.sources
        ):
            raise ValueError("Packet recipient must match all cited sources")
        return self


class ReportCompletion(Schema):
    """Completed AI result for owner-authorized persistence, never a submission receipt."""

    extraction_result: ExtractionResult
    workflow_status: Literal[
        "approved_draft", "rejected_draft", "authority_unavailable", "needs_information", "rejected"
    ]
    candidates: list[IncidentCandidate] = Field(default_factory=list, max_length=20)
    priority: PriorityAssessment | None = None
    recommendation: AuthorityRecommendation | None = None
    packet: ComplaintPacket | None = None


class FollowUpCompletion(Schema):
    """Reviewed citizen-evidence assessment with no authority-status side effect."""

    incident_id: UUID
    assessment: FollowUpAssessment
    attribution: Literal["ai_assessment"]
    observed_at: AwareDatetime
    status: Literal["reviewed_observation", "rejected"]
    updates_authority_status: Literal[False]


class PendingAction(Schema):
    """Private review payload plus the actual LangGraph interrupt identifier."""

    interrupt_id: str = Field(min_length=1)
    kind: ActionKind
    payload: dict[str, Any]


class WorkflowView(Schema):
    """Backend-facing status; excludes raw checkpoint state and internal error messages."""

    workflow_id: UUID
    kind: WorkflowKind
    checkpoint_id: str = Field(min_length=1)
    status: Literal["waiting_for_input", "completed", "incomplete"]
    pending: list[PendingAction] = Field(default_factory=list, max_length=1)
    has_failed_step: bool = False
    output: ReportCompletion | FollowUpCompletion | None = None
