"""Complete report AI workflow, with backend adapters injected explicitly."""

from uuid import UUID

from civicmesh_ai.errors import AIError
from civicmesh_ai.graph.state import WorkflowState
from civicmesh_ai.graph.workflow import add_extraction_flow, initial_state
from civicmesh_ai.nodes.report import build_report_nodes
from civicmesh_ai.schemas import ReportInput
from langgraph.graph import END, StateGraph


def initial_report_state(report: ReportInput, *, owner_id: UUID) -> WorkflowState:
    """Bind a new report workflow to an identity already verified by the backend."""
    return initial_state(report, owner_id=UUID(str(owner_id)))


def build_report_workflow(provider, *, tools, checkpointer):
    """Compose extraction, matching, priority, routing and reviewed complaint drafting."""
    if tools is None or checkpointer is None:
        raise AIError(
            "workflow_not_configured", "Backend tools and a checkpoint store are required."
        )
    graph = StateGraph(WorkflowState)
    add_extraction_flow(graph, provider, tools)
    for name, node in build_report_nodes(provider, tools).items():
        graph.add_node(name, node)
    graph.add_conditional_edges(
        "review_extraction",
        lambda state: (
            "find_incident_candidates" if state["result"]["status"] == "ready_for_backend" else END
        ),
        ["find_incident_candidates", END],
    )
    graph.add_edge("find_incident_candidates", "assess_priority")
    graph.add_edge("assess_priority", "lookup_authority")
    graph.add_conditional_edges(
        "lookup_authority",
        lambda state: (
            "prepare_complaint"
            if state["recommendation"]["authority_id"]
            else "authority_unavailable"
        ),
        ["prepare_complaint", "authority_unavailable"],
    )
    graph.add_edge("prepare_complaint", "review_complaint")
    graph.add_edge("review_complaint", END)
    graph.add_edge("authority_unavailable", END)
    return graph.compile(checkpointer=checkpointer)
