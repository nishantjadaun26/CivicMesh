"""Exercise every real SDK schema and inline media shape against a local HTTP transport."""

import asyncio
import base64
import json
from uuid import UUID

import httpx
import pytest
from civicmesh_ai.assessment import AuthorityRecommendation
from civicmesh_ai.errors import AIError
from civicmesh_ai.media import MediaEvidence
from civicmesh_ai.providers import gemini
from civicmesh_ai.schemas import Extraction, ExtractionRequest
from test_follow_up import request_for_test
from test_report_pipeline import BackendDouble


@pytest.mark.parametrize(
    "operation", ["extract", "priority", "authority", "complaint", "follow_up"]
)
def test_all_sdk_operations_with_local_http(monkeypatch, operation):
    """Validate actual SDK serialization for all output schemas without any live model call."""
    original = gemini.genai.Client
    calls = []
    outputs = {
        "extract": {"category": "water_leak", "summary": "A pipe is leaking.", "language": "hi"},
        "priority": {
            "level": "medium",
            "rationale": "Reported leak.",
            "supporting_observations": ["A pipe is leaking."],
        },
        "authority": {
            "authority_id": str(UUID(int=3)),
            "source_ids": [str(UUID(int=2))],
            "rationale": "Supplied source.",
        },
        "complaint": {
            "subject": "Leak report",
            "observations": ["A pipe is leaking."],
            "requested_action": "Please inspect.",
            "source_ids": [str(UUID(int=2))],
        },
        "follow_up": {
            "outcome": "persists",
            "rationale": "Test comparison.",
            "evidence_ids": [str(UUID(int=1)), str(UUID(int=2))],
        },
    }

    def handle(request):
        """Inspect the wire payload and return a clearly isolated contract fixture."""
        body = json.loads(request.content)
        calls.append(body)
        assert body["generationConfig"]["responseMimeType"] == "application/json"
        assert "tools" not in body
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "role": "model",
                            "parts": [{"text": json.dumps(outputs[operation])}],
                        },
                        "finishReason": "STOP",
                    }
                ]
            },
        )

    def factory(**kwargs):
        """Inject a local transport so SDK serialization cannot reach any network service."""
        kwargs["http_options"].httpx_async_client = httpx.AsyncClient(
            transport=httpx.MockTransport(handle)
        )
        return original(**kwargs)

    monkeypatch.setattr(gemini.genai, "Client", factory)

    async def scenario():
        """Run the actual provider method and verify media survives wire serialization."""
        provider = gemini.GeminiProvider(api_key="isolated-test-key", model="test-only-model")
        extraction = Extraction(category="water_leak", summary="A pipe is leaking.")
        sources = BackendDouble().sources
        recommendation = AuthorityRecommendation(
            authority_id=UUID(int=3), source_ids=[UUID(int=2)], rationale="Test source."
        )
        try:
            if operation == "extract":
                media = [
                    MediaEvidence(
                        evidence_id=UUID(int=1),
                        mime_type="audio/webm",
                        content=b"\x1aE\xdf\xa3test-audio",
                    )
                ]
                result = await provider.extract(
                    ExtractionRequest(evidence_ids=[UUID(int=1)]), media=media
                )
                assert result.language == "hi"
                parts = calls[0]["contents"][0]["parts"]
                assert base64.b64decode(parts[-1]["inlineData"]["data"]) == media[0].content
            elif operation == "priority":
                assert (await provider.assess_priority(extraction)).level == "medium"
            elif operation == "authority":
                assert (
                    await provider.recommend_authority(extraction, sources)
                ).authority_id == UUID(int=3)
            elif operation == "complaint":
                assert (
                    await provider.prepare_complaint(extraction, recommendation, sources)
                ).source_ids == [UUID(int=2)]
            else:
                media = [
                    MediaEvidence(
                        evidence_id=UUID(int=i), mime_type="image/png", content=b"\x89PNG\r\n\x1a\n"
                    )
                    for i in (1, 2)
                ]
                assert (
                    await provider.assess_follow_up(request_for_test(), media=media)
                ).outcome == "persists"
            assert len(calls) == 1
        finally:
            await provider.close()

    asyncio.run(scenario())


def test_provider_refuses_missing_media_and_unsupported_routing_before_request(monkeypatch):
    """Reject incomplete evidence bindings without paying for a model request."""
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    generate = AsyncMock()
    monkeypatch.setattr(
        gemini.genai,
        "Client",
        lambda **kwargs: SimpleNamespace(
            aio=SimpleNamespace(models=SimpleNamespace(generate_content=generate))
        ),
    )
    provider = gemini.GeminiProvider(api_key="isolated-test-key", model="test-model")

    async def scenario():
        """No source produces unknown routing; no bound bytes produces an explicit error."""
        unknown = await provider.recommend_authority(Extraction(), [])
        assert unknown.authority_id is None
        with pytest.raises(AIError):
            await provider.extract(ExtractionRequest(evidence_ids=[UUID(int=1)]))
        with pytest.raises(AIError):
            await provider.prepare_complaint(Extraction(), unknown, [])
        generate.assert_not_awaited()

    asyncio.run(scenario())
