from typing import Protocol

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph

from app.ai.graph.state import WorkflowState
from app.ai.nodes.workflow import build_nodes
from app.ai.tools.interfaces import BackendTools, ExtractionProvider


class CheckpointStore(Protocol):
    """Worker supplies an initialized durable saver; no implicit in-memory default."""

    def saver(self) -> BaseCheckpointSaver: ...


def build_workflow(provider: ExtractionProvider, tools: BackendTools, store: CheckpointStore):
    graph = StateGraph(WorkflowState)
    for name, node in build_nodes(provider, tools).items():
        graph.add_node(name, node)
    graph.add_edge(START, "extract_report")
    graph.add_edge("extract_report", "identify_missing_information")
    graph.add_conditional_edges(
        "identify_missing_information",
        lambda s: (
            "request_clarification" if s["missing_information"] else "find_incident_candidates"
        ),
    )
    # End after clarification: worker must merge answers into validated input and
    # re-run extraction; never silently continue using incomplete extraction.
    graph.add_edge("request_clarification", END)
    chain = [
        "find_incident_candidates",
        "assess_priority",
        "lookup_authority",
        "prepare_complaint",
        "review_complaint",
    ]
    for source, target in zip(chain, chain[1:]):
        graph.add_edge(source, target)
    graph.add_edge("review_complaint", END)
    graph.add_edge("assess_follow_up", END)
    return graph.compile(checkpointer=store.saver())


def build_follow_up_workflow(
    provider: ExtractionProvider, tools: BackendTools, store: CheckpointStore
):
    graph = StateGraph(WorkflowState)
    graph.add_node("assess_follow_up", build_nodes(provider, tools)["assess_follow_up"])
    graph.add_edge(START, "assess_follow_up")
    graph.add_edge("assess_follow_up", END)
    return graph.compile(checkpointer=store.saver())
