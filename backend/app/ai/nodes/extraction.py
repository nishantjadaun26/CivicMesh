from civicmesh_ai.graph.state import WorkflowState
from civicmesh_ai.providers.base import ExtractionProvider
from civicmesh_ai.schemas import (
    Clarification,
    Extraction,
    ExtractionRequest,
    ExtractionResult,
    ReportInput,
    ReviewDecision,
)
from langgraph.types import interrupt

QUESTIONS = {
    "category": "Is this garbage accumulation or a water leak?",
    "confirmed_location": "Please confirm the latitude and longitude of this issue.",
    "description": "What did you observe at the location?",
    "category_conflict": "The selected category and description differ. Please clarify the issue.",
}


def context(state: WorkflowState):
    report = ReportInput.model_validate(state["report"])
    answers = [Clarification.model_validate(answer) for answer in state.get("answers", [])]
    # Validation bounds history before it can cause further model requests.
    request = ExtractionRequest(text=report.text, clarifications=answers)
    category, location = report.category, report.location
    for answer in answers:
        category = answer.category if answer.category is not None else category
        location = answer.location if answer.location is not None else location
    return report, request, category, location


def build_nodes(provider: ExtractionProvider):
    async def extract_report(state: WorkflowState):
        _, request, _, _ = context(state)
        extraction = Extraction.model_validate(await provider.extract(request))
        return {"extraction": extraction.model_dump(mode="json")}

    def identify_missing_information(state: WorkflowState):
        _, _, category, location = context(state)
        extraction = Extraction.model_validate(state["extraction"])
        missing = []
        # Unsupported text is not made in-scope merely by selecting a category.
        if extraction.category is None:
            missing.append("category")
        if location is None:
            missing.append("confirmed_location")
        if extraction.summary is None:
            missing.append("description")
        if category and extraction.category and category != extraction.category:
            missing.append("category_conflict")
        return {"missing_fields": missing}

    def request_clarification(state: WorkflowState):
        reply = interrupt(
            {
                "kind": "clarification",
                "questions": [
                    {"field": field, "question": QUESTIONS[field]}
                    for field in state["missing_fields"]
                ],
                "round": len(state.get("answers", [])) + 1,
            }
        )
        answer = Clarification.model_validate(reply)
        answers = [*state.get("answers", []), answer.model_dump(mode="json")]
        # Keep the original report unchanged and retain a separate answer history.
        context({**state, "answers": answers})
        return {"answers": answers}

    def finish(state: WorkflowState, status: str):
        report, _, category, location = context(state)
        extraction = Extraction.model_validate(state["extraction"])
        result = ExtractionResult(
            report_id=report.report_id,
            extraction=extraction,
            category=category or extraction.category,
            location=location,
            status=status,
            missing_fields=state["missing_fields"],
        )
        return {"result": result.model_dump(mode="json")}

    def review_extraction(state: WorkflowState):
        _, _, category, location = context(state)
        reply = interrupt(
            {
                "kind": "extraction_review",
                "extraction": state["extraction"],
                "category": category or state["extraction"]["category"],
                "location": location.model_dump(mode="json") if location else None,
                "notice": "Approval hands off to backend; it sends no complaint.",
            }
        )
        decision = ReviewDecision.model_validate(reply)
        return finish(state, "ready_for_backend" if decision.approved else "rejected")

    def needs_information(state: WorkflowState):
        return finish(state, "needs_information")

    return {
        "extract_report": extract_report,
        "identify_missing_information": identify_missing_information,
        "request_clarification": request_clarification,
        "review_extraction": review_extraction,
        "needs_information": needs_information,
    }
