import pytest
from langgraph.checkpoint.memory import InMemorySaver

from app.ai.graph.workflow import build_workflow
from app.ai.nodes.workflow import build_nodes
from app.core.errors import ServiceError
from app.schemas.contracts import Extraction


def test_graph_compiles_with_explicit_test_only_saver():
    class Store:
        def saver(self):
            return InMemorySaver()

    graph = build_workflow(None, None, Store())
    assert "request_clarification" in graph.get_graph().nodes
    assert "review_complaint" in graph.get_graph().nodes


def test_missing_information_is_not_invented():
    nodes = build_nodes(None, None)
    assert nodes["identify_missing_information"]({"extraction": Extraction()}) == {
        "missing_information": ["category"]
    }
    with pytest.raises(ServiceError) as exc:
        nodes["assess_priority"]({})
    assert exc.value.status == 501
