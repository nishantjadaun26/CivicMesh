"""Full report processing with deterministic provenance checks and final human review."""

from civicmesh_ai.assessment import (
    AuthorityRecommendation,
    IncidentCandidate,
    OfficialSource,
)
from civicmesh_ai.errors import AIError
from civicmesh_ai.graph.state import WorkflowState
from civicmesh_ai.identity import owner
from civicmesh_ai.nodes.extraction import context
from civicmesh_ai.schemas import Extraction, ReviewDecision
from civicmesh_ai.validation import validate_complaint, validate_priority, validate_recommendation
from langgraph.types import interrupt


def backend_context(state: WorkflowState):
    """Use reviewed category and citizen-confirmed location for all backend lookups."""
    report, _, category, location = context(state)
    extraction = Extraction.model_validate(state["extraction"])
    category = category or extraction.category
    if category is None or location is None:
        raise AIError("incomplete_report", "Category and confirmed location are required.")
    return {
        "report_id": report.report_id,
        "owner_id": owner(state),
        "category": category,
        "location": location,
    }


def build_report_nodes(provider, tools):
    """Build AI-owned orchestration while delegating data access to backend tools."""

    async def find_incident_candidates(state: WorkflowState):
        """Return validated suggestions without merging or modifying original reports."""
        data = backend_context(state)
        raw = await tools.incident_candidates(**data)
        if len(raw) > 20:
            raise AIError("invalid_candidates", "Backend returned too many matching candidates.")
        candidates = [IncidentCandidate.model_validate(item) for item in raw]
        if any(item.category != data["category"] for item in candidates):
            raise AIError("invalid_candidates", "Candidate category does not match the report.")
        if len({item.incident_id for item in candidates}) != len(candidates):
            raise AIError("invalid_candidates", "Candidate identifiers must be unique.")
        return {"candidates": [item.model_dump(mode="json") for item in candidates]}

    async def assess_priority(state: WorkflowState):
        """Validate advisory priority against exact approved report observations."""
        extraction = Extraction.model_validate(state["extraction"])
        value = validate_priority(await provider.assess_priority(extraction), extraction)
        return {"priority": value.model_dump(mode="json")}

    async def lookup_authority(state: WorkflowState):
        """Ask only backend-provided verified sources; absent sources stay unavailable."""
        raw = await tools.authority_sources(**backend_context(state))
        if len(raw) > 10:
            raise AIError("invalid_sources", "Backend returned too many official sources.")
        sources = [OfficialSource.model_validate(item) for item in raw]
        if len({source.document_id for source in sources}) != len(sources):
            raise AIError("invalid_sources", "Source identifiers must be unique.")
        if sources:
            recommendation = await provider.recommend_authority(
                Extraction.model_validate(state["extraction"]), sources
            )
        else:
            recommendation = AuthorityRecommendation(
                rationale="No verified official sources were supplied."
            )
        recommendation = validate_recommendation(recommendation, sources)
        return {
            "sources": [s.model_dump(mode="json") for s in sources],
            "recommendation": recommendation.model_dump(mode="json"),
        }

    def authority_unavailable(state: WorkflowState):
        """End honestly when evidence does not support a recipient; create no complaint."""
        return {"workflow_status": "authority_unavailable"}

    async def prepare_complaint(state: WorkflowState):
        """Create a private draft packet with trusted recipient, provenance and evidence IDs."""
        report, _, _, location = context(state)
        extraction = Extraction.model_validate(state["extraction"])
        sources = [OfficialSource.model_validate(s) for s in state["sources"]]
        recommendation = AuthorityRecommendation.model_validate(state["recommendation"])
        content = validate_complaint(
            await provider.prepare_complaint(extraction, recommendation, sources),
            extraction,
            recommendation,
            sources,
        )
        selected = [s for s in sources if s.document_id in content.source_ids]
        if len({(s.authority_name, s.jurisdiction) for s in selected}) != 1:
            raise AIError("invalid_sources", "Recipient source metadata is inconsistent.")
        recipient = selected[0]
        packet = {
            "report_id": str(report.report_id),
            "authority_id": str(recipient.authority_id),
            "authority_name": recipient.authority_name,
            "jurisdiction": recipient.jurisdiction,
            "location": location.model_dump(mode="json"),
            "content": content.model_dump(mode="json"),
            "sources": [s.model_dump(mode="json") for s in selected],
            "evidence_ids": [str(eid) for eid in report.evidence_ids],
            "authority_status": "unknown",
            "submitted": False,
        }
        return {"packet": packet, "workflow_status": "awaiting_complaint_review"}

    def review_complaint(state: WorkflowState):
        """Require explicit approval of the exact packet; never dispatch externally."""
        reply = interrupt(
            {
                "kind": "complaint_review",
                "packet": state["packet"],
                "priority": state["priority"],
                "candidates": state["candidates"],
                "notice": "This is a draft. Approval does not submit it or merge incidents.",
            }
        )
        decision = ReviewDecision.model_validate(reply)
        return {"workflow_status": "approved_draft" if decision.approved else "rejected_draft"}

    return {
        "find_incident_candidates": find_incident_candidates,
        "assess_priority": assess_priority,
        "lookup_authority": lookup_authority,
        "authority_unavailable": authority_unavailable,
        "prepare_complaint": prepare_complaint,
        "review_complaint": review_complaint,
    }
