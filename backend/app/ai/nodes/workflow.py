from langgraph.types import interrupt

from app.ai.graph.state import WorkflowState
from app.ai.tools.interfaces import BackendTools, ExtractionProvider
from app.core.errors import pending
from app.schemas.contracts import Answers


def build_nodes(provider: ExtractionProvider, tools: BackendTools):
    async def extract_report(state: WorkflowState):
        return {"extraction": await provider.extract(state["text"])}

    def identify_missing_information(state: WorkflowState):
        extraction = state["extraction"]
        missing = list(extraction.missing_information)
        if extraction.category is None:
            missing.append("category")
        return {"missing_information": list(dict.fromkeys(missing))}

    def request_clarification(state: WorkflowState):
        answers = interrupt({"kind": "clarification", "questions": state["missing_information"]})
        # Resume handlers must verify owner and bound answer sizes before re-extraction.
        parsed = Answers.model_validate(answers)
        return {"clarification_answers": parsed.answers}

    async def find_incident_candidates(state: WorkflowState):
        return {"candidate_ids": await tools.find_candidates(state["report_id"], state["owner_id"])}

    def assess_priority(state: WorkflowState):
        pending("Evidence-backed priority assessment")

    async def lookup_authority(state: WorkflowState):
        return {
            "authority_source_ids": await tools.lookup_authority(
                state["report_id"], state["owner_id"]
            )
        }

    def prepare_complaint(state: WorkflowState):
        pending("Source-backed complaint drafting")

    def review_complaint(state: WorkflowState):
        decision = interrupt(
            {"kind": "external_action_review", "draft": state.get("complaint_draft")}
        )
        return {"review_approved": decision is True}

    def assess_follow_up(state: WorkflowState):
        pending("Evidence-backed follow-up assessment")

    return {
        name: value
        for name, value in locals().copy().items()
        if callable(value) and name not in {"provider", "tools"}
    }
