from civicmesh_ai.errors import AIError
from civicmesh_ai.graph.state import WorkflowState
from civicmesh_ai.nodes.extraction import build_nodes
from civicmesh_ai.providers.base import ExtractionProvider
from civicmesh_ai.schemas import MAX_CLARIFICATION_ROUNDS, ReportInput
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph


def initial_state(report: ReportInput) -> WorkflowState:
    report = ReportInput.model_validate(report)
    return {"report": report.model_dump(mode="json"), "answers": []}


def build_workflow(provider: ExtractionProvider, *, checkpointer: BaseCheckpointSaver):
    """Caller supplies persistence. Production durability is backend-owned and unverified."""
    if checkpointer is None:
        raise AIError("checkpoint_required", "Provide a checkpoint store for resumable execution.")
    graph = StateGraph(WorkflowState)
    for name, node in build_nodes(provider).items():
        graph.add_node(name, node)
    graph.add_edge(START, "extract_report")
    graph.add_edge("extract_report", "identify_missing_information")

    def next_node(state):
        if not state["missing_fields"]:
            return "review_extraction"
        if len(state.get("answers", [])) >= MAX_CLARIFICATION_ROUNDS:
            return "needs_information"
        return "request_clarification"

    graph.add_conditional_edges(
        "identify_missing_information",
        next_node,
        ["request_clarification", "review_extraction", "needs_information"],
    )
    graph.add_edge("request_clarification", "extract_report")
    graph.add_edge("review_extraction", END)
    graph.add_edge("needs_information", END)
    return graph.compile(checkpointer=checkpointer)
