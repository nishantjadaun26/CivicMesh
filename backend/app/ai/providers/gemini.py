import os

import httpx
from civicmesh_ai.errors import AIError
from civicmesh_ai.prompts import EXTRACTION_SYSTEM
from civicmesh_ai.schemas import Extraction, ExtractionRequest
from google import genai
from google.genai import errors, types
from pydantic import ValidationError


class GeminiProvider:
    """One bounded request. Persistent retries and their budgets belong to the worker."""

    def __init__(self, *, api_key: str, model: str):
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
        return cls(api_key=os.getenv("GEMINI_API_KEY", ""), model=os.getenv("GEMINI_MODEL", ""))

    async def extract(self, request: ExtractionRequest) -> Extraction:
        request = ExtractionRequest.model_validate(request)
        # Coordinates remain in the trusted workflow context, not the model prompt.
        evidence = request.model_dump_json(exclude={"clarifications": {"__all__": {"location"}}})
        try:
            response = await self.client.aio.models.generate_content(
                model=self.model,
                contents=evidence,
                config=types.GenerateContentConfig(
                    system_instruction=EXTRACTION_SYSTEM,
                    response_mime_type="application/json",
                    response_schema=Extraction,
                    max_output_tokens=2048,
                    temperature=0,
                ),
            )
        except errors.APIError as exc:
            transient = exc.code == 429 or (isinstance(exc.code, int) and exc.code >= 500)
            raise AIError(
                "provider_error", "AI provider request failed.", retryable=transient
            ) from None
        except (httpx.HTTPError, TimeoutError, ConnectionError):
            raise AIError(
                "provider_unavailable", "AI provider is unavailable.", retryable=True
            ) from None
        if not response.text:
            raise AIError("invalid_model_output", "AI returned no structured output.")
        try:
            return Extraction.model_validate_json(response.text)
        except ValidationError:
            raise AIError(
                "invalid_model_output", "AI output did not match the extraction schema."
            ) from None

    async def close(self):
        await self.client.aio.aclose()
