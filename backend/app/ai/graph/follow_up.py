"""Reviewed follow-up observations, kept separate from authority updates."""

from uuid import UUID

from civicmesh_ai.assessment import FollowUpAssessment, FollowUpInput
from civicmesh_ai.errors import AIError
from civicmesh_ai.follow_up import sufficient_comparison, validate_follow_up
from civicmesh_ai.graph.state import WorkflowState
from civicmesh_ai.identity import owner
from civicmesh_ai.media import load_media
from civicmesh_ai.schemas import ReviewDecision
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt


def initial_follow_up_state(request: FollowUpInput, *, owner_id: UUID) -> WorkflowState:
    """Create private checkpoint state using existing incident/evidence identifiers."""
    request = FollowUpInput.model_validate(request)
    return {"follow_up": request.model_dump(mode="json"), "owner_id": str(UUID(str(owner_id)))}


def build_follow_up_workflow(provider, *, tools, checkpointer):
    """Build evidence assessment and human review without any authority-status mutation."""
    if tools is None or checkpointer is None:
        raise AIError(
            "workflow_not_configured", "Backend tools and a checkpoint store are required."
        )

    async def assess_follow_up(state):
        """Return insufficient evidence before paying for an unsupported visual comparison."""
        request = FollowUpInput.model_validate(state["follow_up"])
        owner_id = owner(state)
        if (
            request.same_location_confirmed
            and request.baseline_evidence_ids
            and request.follow_up_evidence_ids
        ):
            media = await load_media(
                tools,
                owner_id=owner_id,
                report_id=None,
                incident_id=request.incident_id,
                evidence_ids=request.baseline_evidence_ids + request.follow_up_evidence_ids,
            )
        else:
            media = []
        if sufficient_comparison(request, media):
            assessment = validate_follow_up(
                await provider.assess_follow_up(request, media=media), request, media
            )
        else:
            assessment = FollowUpAssessment(
                outcome="insufficient_evidence",
                rationale="Confirmed same-location baseline and follow-up images are required.",
                limitations=[
                    "No visual condition can be established from the supplied comparison."
                ],
            )
        return {"assessment": assessment.model_dump(mode="json")}

    def review_follow_up(state):
        """Publish nothing automatically and label every reviewed outcome as an AI observation."""
        reply = interrupt(
            {
                "kind": "follow_up_review",
                "assessment": state["assessment"],
                "notice": "Citizen evidence and AI observations are not official resolution updates.",
            }
        )
        decision = ReviewDecision.model_validate(reply)
        request = FollowUpInput.model_validate(state["follow_up"])
        return {
            "result": {
                "incident_id": str(request.incident_id),
                "assessment": state["assessment"],
                "attribution": "ai_assessment",
                "observed_at": request.observed_at.isoformat(),
                "status": "reviewed_observation" if decision.approved else "rejected",
                "updates_authority_status": False,
            }
        }

    graph = StateGraph(WorkflowState)
    graph.add_node("assess_follow_up", assess_follow_up)
    graph.add_node("review_follow_up", review_follow_up)
    graph.add_edge(START, "assess_follow_up")
    graph.add_edge("assess_follow_up", "review_follow_up")
    graph.add_edge("review_follow_up", END)
    return graph.compile(checkpointer=checkpointer)
