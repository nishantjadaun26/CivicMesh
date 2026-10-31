"""Conservative visual follow-up checks with isolated before/after fixtures."""

import asyncio
from datetime import datetime, timezone
from uuid import UUID

import pytest
from civicmesh_ai.assessment import FollowUpAssessment, FollowUpInput
from civicmesh_ai.errors import AIError
from civicmesh_ai.graph.follow_up import build_follow_up_workflow, initial_follow_up_state
from civicmesh_ai.media import MediaEvidence
from civicmesh_ai.schemas import Extraction
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command


class FollowUpProvider:
    """Test-only assessment provider, never a runtime fallback."""

    def __init__(self, outcome="appears_resolved", evidence_ids=None):
        """Initialize isolated test state and record expected provider interactions."""
        self.calls = 0
        self.outcome = outcome
        self.ids = evidence_ids if evidence_ids is not None else [UUID(int=1), UUID(int=2)]

    async def assess_follow_up(self, request, *, media):
        """Return a controlled condition solely for orchestration/validation tests."""
        self.calls += 1
        return FollowUpAssessment(
            outcome=self.outcome,
            rationale="Test comparison.",
            evidence_ids=self.ids,
            limitations=["A photo cannot prove an official repair."],
        )


class EvidenceTools:
    """Return only test image headers and record the owner passed by the workflow."""

    def __init__(self):
        """Initialize isolated test state and record expected provider interactions."""
        self.calls = []

    async def load_evidence(self, **kwargs):
        """Provide distinct before/after fixture media without any storage connection."""
        self.calls.append(kwargs)
        return [
            MediaEvidence(evidence_id=eid, mime_type="image/png", content=b"\x89PNG\r\n\x1a\n")
            for eid in kwargs["evidence_ids"]
        ]


def request_for_test(*, same_location=True, before=True, after=True):
    """Construct an isolated comparison; these IDs never enter product/demo data."""
    return FollowUpInput(
        incident_id=UUID(int=3),
        baseline=Extraction(category="garbage", summary="Garbage reported."),
        baseline_evidence_ids=[UUID(int=1)] if before else [],
        follow_up_evidence_ids=[UUID(int=2)] if after else [],
        observed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        same_location_confirmed=same_location,
    )


@pytest.mark.parametrize(
    "outcome", ["appears_resolved", "partly_resolved", "persists", "insufficient_evidence"]
)
def test_all_follow_up_outcomes_require_review_and_never_update_authority(outcome):
    """Record an attributed observation only after review, with no official-status mutation."""

    async def scenario():
        """Exercise all follow up outcomes require review and never update authority in one event loop."""
        provider, tools = FollowUpProvider(outcome), EvidenceTools()
        graph = build_follow_up_workflow(provider, tools=tools, checkpointer=InMemorySaver())
        config = {"configurable": {"thread_id": outcome}}
        result = await graph.ainvoke(
            initial_follow_up_state(request_for_test(), owner_id=UUID(int=9)), config
        )
        assert result["__interrupt__"][0].value["kind"] == "follow_up_review"
        result = await graph.ainvoke(Command(resume={"approved": True}), config)
        assert result["result"]["assessment"]["outcome"] == outcome
        assert result["result"]["updates_authority_status"] is False
        assert result["result"]["attribution"] == "ai_assessment"
        assert provider.calls == 1
        assert tools.calls[0]["owner_id"] == UUID(int=9)

    asyncio.run(scenario())


@pytest.mark.parametrize("options", [{"same_location": False}, {"before": False}, {"after": False}])
def test_insufficient_comparison_skips_model_and_storage(options):
    """Missing comparable evidence yields a policy outcome, never a fabricated assessment."""

    async def scenario():
        """Exercise insufficient comparison skips model and storage in one event loop."""
        provider, tools = FollowUpProvider(), EvidenceTools()
        graph = build_follow_up_workflow(provider, tools=tools, checkpointer=InMemorySaver())
        config = {"configurable": {"thread_id": "insufficient"}}
        result = await graph.ainvoke(
            initial_follow_up_state(request_for_test(**options), owner_id=UUID(int=9)), config
        )
        assert result["assessment"]["outcome"] == "insufficient_evidence"
        assert provider.calls == 0
        assert not tools.calls
        result = await graph.ainvoke(Command(resume={"approved": False}), config)
        assert result["result"]["status"] == "rejected"

    asyncio.run(scenario())


@pytest.mark.parametrize("ids", [[UUID(int=99)], [UUID(int=2)]])
def test_fabricated_or_one_sided_follow_up_citations_are_rejected(ids):
    """A resolution claim needs actual supplied before and after image references."""

    async def scenario():
        """Exercise fabricated or one sided follow up citations are rejected in one event loop."""
        graph = build_follow_up_workflow(
            FollowUpProvider(evidence_ids=ids), tools=EvidenceTools(), checkpointer=InMemorySaver()
        )
        with pytest.raises(AIError):
            await graph.ainvoke(
                initial_follow_up_state(request_for_test(), owner_id=UUID(int=9)),
                {"configurable": {"thread_id": "invalid-follow-up"}},
            )

    asyncio.run(scenario())
