from typing import TypedDict


class WorkflowState(TypedDict, total=False):
    """Private checkpoint data; raw media and credentials are never placed in state."""

    # JSON-compatible checkpoint values. Revalidate at node boundaries.
    report: dict
    answers: list[dict]
    extraction: dict
    missing_fields: list[str]
    result: dict
    owner_id: str
    candidates: list[dict]
    priority: dict
    sources: list[dict]
    recommendation: dict
    packet: dict
    workflow_status: str
    follow_up: dict
    assessment: dict
