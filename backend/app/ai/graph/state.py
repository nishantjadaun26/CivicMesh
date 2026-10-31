from typing import TypedDict


class WorkflowState(TypedDict, total=False):
    # JSON-compatible checkpoint values. Revalidate at node boundaries.
    report: dict
    answers: list[dict]
    extraction: dict
    missing_fields: list[str]
    result: dict
