"""Full report workflow against isolated backend/provider doubles, with no live services."""

import asyncio
import json
from datetime import datetime, timezone
from uuid import UUID

import pytest
from civicmesh_ai.assessment import (
    AuthorityRecommendation,
    ComplaintContent,
    IncidentCandidate,
    OfficialSource,
    PriorityAssessment,
)
from civicmesh_ai.errors import AIError
from civicmesh_ai.graph.report import build_report_workflow, initial_report_state
from civicmesh_ai.graph.workflow import initial_state
from civicmesh_ai.media import MediaEvidence
from civicmesh_ai.schemas import Extraction, ReportInput
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command


class BackendDouble:
    """Backend fixture that records identity and never fetches anything."""

    def __init__(self):
        """Initialize isolated test state and record expected provider interactions."""
        self.calls = []
        self.sources = [
            OfficialSource(
                document_id=UUID(int=2),
                authority_id=UUID(int=3),
                authority_name="Isolated test authority",
                jurisdiction="Test-only jurisdiction",
                url="https://official-source.invalid/water",
                retrieved_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                verified_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                supporting_passage="Test water responsibility.",
            )
        ]
        self.media = []

    async def load_evidence(self, **kwargs):
        """Return explicitly installed media fixtures for authorization propagation tests."""
        self.calls.append(("media", kwargs))
        return self.media

    async def incident_candidates(self, **kwargs):
        """Return a test candidate without mutating any membership or real data."""
        self.calls.append(("candidates", kwargs))
        return [
            IncidentCandidate(
                incident_id=UUID(int=4), category="water_leak", reason="Test candidate."
            )
        ]

    async def authority_sources(self, **kwargs):
        """Return test-only provenance; it cannot be loaded by the application."""
        self.calls.append(("sources", kwargs))
        return self.sources


class ProviderDouble:
    """Deterministic outputs are limited to this isolated test fixture."""

    def __init__(self):
        """Initialize isolated test state and record expected provider interactions."""
        self.calls = []
        self.recommendation = AuthorityRecommendation(
            authority_id=UUID(int=3), source_ids=[UUID(int=2)], rationale="Test source."
        )
        self.content = ComplaintContent(
            subject="Test draft",
            observations=["A pipe is leaking."],
            requested_action="Please inspect the reported leak.",
            source_ids=[UUID(int=2)],
        )

    async def extract(self, request, *, media=()):
        """Record extraction inputs without calling an external model."""
        self.calls.append(("extract", request))
        return Extraction(category="water_leak", summary="A pipe is leaking.", language="en")

    async def assess_priority(self, extraction):
        """Supply an exact supported quote for the priority validation boundary."""
        self.calls.append(("priority", extraction))
        return PriorityAssessment(
            level="medium",
            rationale="Reported leak.",
            supporting_observations=["A pipe is leaking."],
        )

    async def recommend_authority(self, extraction, sources):
        """Expose mutable test recommendation for adversarial citation scenarios."""
        self.calls.append(("authority", sources))
        return self.recommendation

    async def prepare_complaint(self, extraction, recommendation, sources):
        """Expose mutable draft content for unsupported observation tests."""
        self.calls.append(("complaint", sources))
        return self.content


def test_complete_report_requires_two_reviews_and_never_submits(report):
    """Run extraction, matching, priority and drafting with identity/provenance preserved."""

    async def scenario():
        """Exercise complete report requires two reviews and never submits in one event loop."""
        tools, provider = BackendDouble(), ProviderDouble()
        graph = build_report_workflow(provider, tools=tools, checkpointer=InMemorySaver())
        config = {"configurable": {"thread_id": "full-report"}}
        state = await graph.ainvoke(initial_report_state(report, owner_id=UUID(int=9)), config)
        assert state["__interrupt__"][0].value["kind"] == "extraction_review"
        assert not tools.calls
        state = await graph.ainvoke(Command(resume={"approved": True}), config)
        assert state["__interrupt__"][0].value["kind"] == "complaint_review"
        assert state["packet"]["submitted"] is False
        assert state["packet"]["authority_status"] == "unknown"
        assert state["packet"]["sources"][0]["document_id"] == str(UUID(int=2))
        assert all(call[1]["owner_id"] == UUID(int=9) for call in tools.calls)
        assert tools.calls[0][1]["location"] == report.location
        call_count = len(provider.calls)
        state = await graph.ainvoke(Command(resume={"approved": True}), config)
        assert state["workflow_status"] == "approved_draft"
        assert state["packet"]["submitted"] is False
        assert len(provider.calls) == call_count

    asyncio.run(scenario())


def test_no_verified_sources_produces_no_complaint_or_routing_model_call(report):
    """An empty real retrieval result is an explicit unavailable outcome, not fake routing."""

    async def scenario():
        """Exercise no verified sources produces no complaint or routing model call in one event loop."""
        tools, provider = BackendDouble(), ProviderDouble()
        tools.sources = []
        graph = build_report_workflow(provider, tools=tools, checkpointer=InMemorySaver())
        config = {"configurable": {"thread_id": "no-sources"}}
        await graph.ainvoke(initial_report_state(report, owner_id=UUID(int=9)), config)
        state = await graph.ainvoke(Command(resume={"approved": True}), config)
        assert state["workflow_status"] == "authority_unavailable"
        assert "packet" not in state
        assert [call[0] for call in provider.calls] == ["extract", "priority"]

    asyncio.run(scenario())


@pytest.mark.parametrize("fault", ["authority", "source", "observation"])
def test_fabricated_routing_and_complaint_content_are_rejected(report, fault):
    """Known schema shapes do not permit invented recipients, citations or factual claims."""

    async def scenario():
        """Exercise fabricated routing and complaint content are rejected in one event loop."""
        tools, provider = BackendDouble(), ProviderDouble()
        if fault == "authority":
            provider.recommendation = AuthorityRecommendation(
                authority_id=UUID(int=99), source_ids=[UUID(int=2)], rationale="Unsupported."
            )
        elif fault == "source":
            provider.content = provider.content.model_copy(update={"source_ids": [UUID(int=99)]})
        else:
            provider.content = provider.content.model_copy(
                update={"observations": ["Government repaired everything."]}
            )
        graph = build_report_workflow(provider, tools=tools, checkpointer=InMemorySaver())
        config = {"configurable": {"thread_id": "invalid-" + fault}}
        await graph.ainvoke(initial_report_state(report, owner_id=UUID(int=9)), config)
        with pytest.raises(AIError):
            await graph.ainvoke(Command(resume={"approved": True}), config)

    asyncio.run(scenario())


def test_private_media_is_loaded_with_owner_and_not_checkpointed(report):
    """Store only real evidence references in checkpoint state, not binary content."""

    async def scenario():
        """Exercise private media is loaded with owner and not checkpointed in one event loop."""
        tools, provider = BackendDouble(), ProviderDouble()
        tools.media = [
            MediaEvidence(
                evidence_id=UUID(int=5),
                mime_type="image/png",
                content=b"\x89PNG\r\n\x1a\nprivate-bytes",
            )
        ]
        media_report = ReportInput(
            report_id=report.report_id, evidence_ids=[UUID(int=5)], location=report.location
        )
        graph = build_report_workflow(provider, tools=tools, checkpointer=InMemorySaver())
        config = {"configurable": {"thread_id": "media"}}
        await graph.ainvoke(initial_report_state(media_report, owner_id=UUID(int=9)), config)
        snapshot = await graph.aget_state(config)
        assert "private-bytes" not in json.dumps(snapshot.values)
        assert tools.calls[0][1]["owner_id"] == UUID(int=9)
        assert tools.calls[0][1]["report_id"] == report.report_id

    asyncio.run(scenario())


def test_missing_owner_rejects_before_paid_or_backend_calls(report):
    """The full workflow refuses missing authenticated context before processing."""

    async def scenario():
        """Exercise missing owner rejects before paid or backend calls in one event loop."""
        tools, provider = BackendDouble(), ProviderDouble()
        graph = build_report_workflow(provider, tools=tools, checkpointer=InMemorySaver())
        with pytest.raises(AIError, match="owner context"):
            await graph.ainvoke(initial_state(report), {"configurable": {"thread_id": "no-owner"}})
        assert not provider.calls and not tools.calls

    asyncio.run(scenario())
