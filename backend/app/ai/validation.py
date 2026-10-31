"""Deterministic evidence binding around otherwise untrusted model outputs."""

from civicmesh_ai.assessment import (
    AuthorityRecommendation,
    ComplaintContent,
    OfficialSource,
    PriorityAssessment,
)
from civicmesh_ai.errors import AIError
from civicmesh_ai.schemas import Extraction


def validate_quotes(observations: list[str], extraction: Extraction):
    """Require exact supported excerpts, not newly invented factual observations."""
    available = [value for value in [extraction.summary, extraction.location_description] if value]
    if any(not any(quote in text for text in available) for quote in observations):
        raise AIError("unsupported_observation", "Assessment contains an unsupported observation.")


def validate_priority(value: PriorityAssessment, extraction: Extraction):
    """Validate the schema and bind priority rationale evidence to approved text."""
    value = PriorityAssessment.model_validate(value)
    validate_quotes(value.supporting_observations, extraction)
    return value


def validate_recommendation(value: AuthorityRecommendation, sources: list[OfficialSource]):
    """Reject invented authorities, foreign citations and ambiguous source identifiers."""
    value = AuthorityRecommendation.model_validate(value)
    by_id = {source.document_id: source for source in sources}
    if len(by_id) != len(sources):
        raise AIError("invalid_sources", "Source identifiers must be unique.")
    if any(
        sid not in by_id or by_id[sid].authority_id != value.authority_id
        for sid in value.source_ids
    ):
        raise AIError("unsupported_authority", "Authority recommendation lacks matching sources.")
    return value


def validate_complaint(
    value: ComplaintContent,
    extraction: Extraction,
    recommendation: AuthorityRecommendation,
    sources: list[OfficialSource],
):
    """Bind factual observations and citations before a draft can reach human review."""
    value = ComplaintContent.model_validate(value)
    validate_recommendation(recommendation, sources)
    if recommendation.authority_id is None or not set(value.source_ids).issubset(
        recommendation.source_ids
    ):
        raise AIError(
            "unsupported_source", "Complaint citations must support the recommended authority."
        )
    if len(set(value.source_ids)) != len(value.source_ids):
        raise AIError("unsupported_source", "Complaint source identifiers must be unique.")
    validate_quotes(value.observations, extraction)
    return value
