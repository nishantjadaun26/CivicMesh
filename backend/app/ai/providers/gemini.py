"""Gemini operations with bounded requests, validated output and no executable tools."""

import json
import os
from collections.abc import Sequence
from typing import TypeVar

import httpx
from civicmesh_ai.assessment import (
    AuthorityRecommendation,
    ComplaintContent,
    FollowUpAssessment,
    FollowUpInput,
    OfficialSource,
    PriorityAssessment,
)
from civicmesh_ai.errors import AIError
from civicmesh_ai.media import MediaEvidence, validate_media
from civicmesh_ai.prompts import (
    AUTHORITY_SYSTEM,
    COMPLAINT_SYSTEM,
    EXTRACTION_SYSTEM,
    FOLLOW_UP_SYSTEM,
    PRIORITY_SYSTEM,
)
from civicmesh_ai.schemas import Extraction, ExtractionRequest, Schema
from civicmesh_ai.validation import validate_complaint, validate_priority, validate_recommendation
from google import genai
from google.genai import errors, types
from pydantic import ValidationError

Output = TypeVar("Output", bound=Schema)


class GeminiProvider:
    """One request per operation; worker retries must use a persisted bounded budget."""

    def __init__(self, *, api_key: str, model: str):
        """Require explicit credentials/model and bound SDK timeout and attempt count."""
        if not api_key.strip() or not model.strip():
            raise AIError("ai_not_configured", "Set GEMINI_API_KEY and GEMINI_MODEL.")
        self.model = model
        self.client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(
                timeout=30000, retry_options=types.HttpRetryOptions(attempts=1)
            ),
        )

    @classmethod
    def from_environment(cls):
        """Load backend-only environment variables without guessing a model identifier."""
        return cls(api_key=os.getenv("GEMINI_API_KEY", ""), model=os.getenv("GEMINI_MODEL", ""))

    async def _generate(
        self, schema: type[Output], system: str, evidence: str, media: Sequence[MediaEvidence] = ()
    ) -> Output:
        """Send bounded evidence as user content and sanitize SDK/schema failures."""
        contents = evidence
        if media:
            parts = [types.Part.from_text(text=evidence)]
            for item in media:
                parts.extend(
                    [
                        types.Part.from_text(text=f"Evidence identifier: {item.evidence_id}"),
                        types.Part.from_bytes(data=item.content, mime_type=item.mime_type),
                    ]
                )
            contents = [types.Content(role="user", parts=parts)]
        try:
            response = await self.client.aio.models.generate_content(
                model=self.model,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system,
                    response_mime_type="application/json",
                    response_schema=schema,
                    max_output_tokens=4096,
                ),
            )
            if not response.text:
                raise AIError("invalid_model_output", "AI returned no structured output.")
            return schema.model_validate_json(response.text)
        except errors.APIError as exc:
            transient = exc.code == 429 or (isinstance(exc.code, int) and exc.code >= 500)
            raise AIError(
                "provider_error", "AI provider request failed.", retryable=transient
            ) from None
        except (httpx.HTTPError, TimeoutError, ConnectionError):
            raise AIError(
                "provider_unavailable", "AI provider is unavailable.", retryable=True
            ) from None
        except (ValidationError, ValueError):
            raise AIError(
                "invalid_model_output", "AI output did not match the requested schema."
            ) from None

    async def extract(
        self, request: ExtractionRequest, *, media: Sequence[MediaEvidence] = ()
    ) -> Extraction:
        """Extract Hindi/English text, images and recorded audio without publishing media."""
        request = ExtractionRequest.model_validate(request)
        media = validate_media(media, request.evidence_ids)
        evidence = request.model_dump_json(exclude={"clarifications": {"__all__": {"location"}}})
        return await self._generate(Extraction, EXTRACTION_SYSTEM, evidence, media)

    async def assess_priority(self, extraction: Extraction) -> PriorityAssessment:
        """Return advisory priority with exact supporting excerpts and explicit uncertainty."""
        extraction = Extraction.model_validate(extraction)
        value = await self._generate(
            PriorityAssessment, PRIORITY_SYSTEM, extraction.model_dump_json()
        )
        return validate_priority(value, extraction)

    async def recommend_authority(
        self, extraction: Extraction, sources: list[OfficialSource]
    ) -> AuthorityRecommendation:
        """Recommend only a supplied verified authority; no sources means no model call."""
        extraction = Extraction.model_validate(extraction)
        sources = [OfficialSource.model_validate(source) for source in sources]
        if len(sources) > 10 or len({s.document_id for s in sources}) != len(sources):
            raise AIError(
                "invalid_sources", "Provide at most 10 uniquely identified official sources."
            )
        if not sources:
            return AuthorityRecommendation(rationale="No verified official sources were supplied.")
        evidence = json.dumps(
            {
                "extraction": extraction.model_dump(mode="json"),
                "sources": [source.model_dump(mode="json") for source in sources],
            }
        )
        return validate_recommendation(
            await self._generate(AuthorityRecommendation, AUTHORITY_SYSTEM, evidence), sources
        )

    async def prepare_complaint(
        self,
        extraction: Extraction,
        recommendation: AuthorityRecommendation,
        sources: list[OfficialSource],
    ) -> ComplaintContent:
        """Draft factual content only after routing has supporting official provenance."""
        extraction = Extraction.model_validate(extraction)
        sources = [OfficialSource.model_validate(source) for source in sources]
        recommendation = validate_recommendation(recommendation, sources)
        if recommendation.authority_id is None:
            raise AIError(
                "authority_unavailable", "A supported authority is required for a complaint."
            )
        selected = [s for s in sources if s.document_id in recommendation.source_ids]
        evidence = json.dumps(
            {
                "extraction": extraction.model_dump(mode="json"),
                "recommendation": recommendation.model_dump(mode="json"),
                "sources": [source.model_dump(mode="json") for source in selected],
            }
        )
        value = await self._generate(ComplaintContent, COMPLAINT_SYSTEM, evidence)
        return validate_complaint(value, extraction, recommendation, sources)

    async def assess_follow_up(
        self, request: FollowUpInput, *, media: Sequence[MediaEvidence] = ()
    ) -> FollowUpAssessment:
        """Compare supported before/after images; inadequate inputs fail to insufficient evidence."""
        request = FollowUpInput.model_validate(request)
        media = validate_media(
            media, request.baseline_evidence_ids + request.follow_up_evidence_ids
        )
        from civicmesh_ai.follow_up import sufficient_comparison, validate_follow_up

        if not sufficient_comparison(request, media):
            return FollowUpAssessment(
                outcome="insufficient_evidence",
                rationale="Confirmed same-location baseline and follow-up images are required.",
                limitations=[
                    "No visual condition can be established from the supplied comparison."
                ],
            )
        evidence = request.model_dump_json(exclude={"incident_id"})
        value = await self._generate(FollowUpAssessment, FOLLOW_UP_SYSTEM, evidence, media)
        return validate_follow_up(value, request, media)

    async def close(self):
        """Release asynchronous HTTP resources during worker shutdown."""
        await self.client.aio.aclose()
