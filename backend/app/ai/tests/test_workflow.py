import asyncio

import pytest
from civicmesh_ai.errors import AIError
from civicmesh_ai.graph.workflow import build_workflow, initial_state
from civicmesh_ai.schemas import Extraction, ReportInput
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from pydantic import ValidationError


class TestProvider:
    """Test-only provider, never an application fallback."""

    __test__ = False

    def __init__(self, output=None):
        """Initialize isolated test state and record expected provider interactions."""
        self.output = (
            output
            if output is not None
            else Extraction(
                category="water_leak", summary="Citizen reports a leaking pipe.", language="en"
            )
        )
        self.requests = []

    async def extract(self, request):
        """Provide isolated fixtures for extract verification."""
        self.requests.append(request)
        return self.output


def test_review_pause_and_resume_do_not_repeat_model_call(report):
    """Verify review pause and resume do not repeat model call."""

    async def scenario():
        """Exercise review pause and resume do not repeat model call in one event loop."""
        provider = TestProvider()
        graph = build_workflow(provider, checkpointer=InMemorySaver())
        config = {"configurable": {"thread_id": "test-review"}}
        paused = await graph.ainvoke(initial_state(report), config)
        assert paused["__interrupt__"][0].value["kind"] == "extraction_review"
        assert "result" not in paused
        done = await graph.ainvoke(Command(resume={"approved": True}), config)
        assert done["result"]["status"] == "ready_for_backend"
        assert done["result"]["authority_status"] == "unknown"
        assert len(provider.requests) == 1

    asyncio.run(scenario())


def test_clarification_preserves_original_and_reextracts(report):
    """Verify clarification preserves original and reextracts."""

    async def scenario():
        """Exercise clarification preserves original and reextracts in one event loop."""
        provider = TestProvider()
        graph = build_workflow(provider, checkpointer=InMemorySaver())
        original = ReportInput(report_id=report.report_id, text=report.text)
        config = {"configurable": {"thread_id": "test-clarify"}}
        paused = await graph.ainvoke(initial_state(original), config)
        assert paused["__interrupt__"][0].value["questions"][0]["field"] == "confirmed_location"
        reviewed = await graph.ainvoke(
            Command(
                resume={
                    "text": "The leak is still visible.",
                    "location": report.location.model_dump(mode="json"),
                }
            ),
            config,
        )
        assert reviewed["__interrupt__"][0].value["kind"] == "extraction_review"
        assert reviewed["report"] == original.model_dump(mode="json")
        assert len(provider.requests) == 2
        assert provider.requests[-1].clarifications[0].text == "The leak is still visible."
        done = await graph.ainvoke(Command(resume={"approved": False}), config)
        assert done["result"]["status"] == "rejected"
        assert len(provider.requests) == 2

    asyncio.run(scenario())


def test_three_unanswered_rounds_stop_without_inventing_data(report):
    """Verify three unanswered rounds stop without inventing data."""

    async def scenario():
        """Exercise three unanswered rounds stop without inventing data in one event loop."""
        provider = TestProvider(Extraction())
        graph = build_workflow(provider, checkpointer=InMemorySaver())
        config = {"configurable": {"thread_id": "test-limit"}}
        result = await graph.ainvoke(initial_state(report), config)
        for _ in range(3):
            assert result["__interrupt__"][0].value["kind"] == "clarification"
            result = await graph.ainvoke(Command(resume={"text": "I do not know."}), config)
        assert "__interrupt__" not in result
        assert result["result"]["status"] == "needs_information"
        assert result["result"]["extraction"]["summary"] is None
        assert len(provider.requests) == 4  # Initial extraction plus three clarification rounds.

    asyncio.run(scenario())


def test_category_conflict_cannot_skip_review(report):
    """Verify category conflict cannot skip review."""

    async def scenario():
        """Exercise category conflict cannot skip review in one event loop."""
        provider = TestProvider(Extraction(category="garbage", summary="Garbage reported."))
        graph = build_workflow(provider, checkpointer=InMemorySaver())
        config = {"configurable": {"thread_id": "test-conflict"}}
        result = await graph.ainvoke(initial_state(report), config)
        assert "category_conflict" in result["missing_fields"]
        assert "result" not in result
        result = await graph.ainvoke(Command(resume={"category": "garbage"}), config)
        assert result["__interrupt__"][0].value["kind"] == "extraction_review"

    asyncio.run(scenario())


def test_invalid_resume_is_rejected_before_another_paid_call(report):
    """Verify invalid resume is rejected before another paid call."""

    async def scenario():
        """Exercise invalid resume is rejected before another paid call in one event loop."""
        provider = TestProvider(Extraction())
        graph = build_workflow(provider, checkpointer=InMemorySaver())
        config = {"configurable": {"thread_id": "test-invalid"}}
        await graph.ainvoke(initial_state(report), config)
        with pytest.raises(ValidationError):
            await graph.ainvoke(Command(resume={"owner_id": "injected"}), config)
        assert len(provider.requests) == 1

    asyncio.run(scenario())


def test_threads_keep_separate_state(report):
    """Verify threads keep separate state."""

    async def scenario():
        """Exercise threads keep separate state in one event loop."""
        graph = build_workflow(TestProvider(), checkpointer=InMemorySaver())
        first = {"configurable": {"thread_id": "one"}}
        second = {"configurable": {"thread_id": "two"}}
        await graph.ainvoke(initial_state(report), first)
        await graph.ainvoke(initial_state(report), second)
        await graph.ainvoke(Command(resume={"approved": True}), first)
        snapshot = await graph.aget_state(second)
        assert "result" not in snapshot.values
        assert snapshot.next == ("review_extraction",)

    asyncio.run(scenario())


def test_checkpoint_store_is_required():
    """Verify checkpoint store is required."""
    with pytest.raises(AIError, match="checkpoint"):
        build_workflow(TestProvider(), checkpointer=None)
