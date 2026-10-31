from typing import TypedDict

from app.schemas.contracts import Assessment, Extraction


class WorkflowState(TypedDict, total=False):
    report_id: str
    owner_id: str
    text: str
    extraction: Extraction
    missing_information: list[str]
    clarification_answers: dict[str, str]
    candidate_ids: list[str]
    authority_source_ids: list[str]
    priority: str | None
    complaint_draft: str | None
    observed_condition: Assessment
    review_approved: bool
