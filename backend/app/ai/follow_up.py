"""Conservative follow-up comparison and citation checks independent of the model."""

from collections.abc import Sequence
from hashlib import sha256

from civicmesh_ai.assessment import FollowUpAssessment, FollowUpInput
from civicmesh_ai.errors import AIError
from civicmesh_ai.media import MediaEvidence


def sufficient_comparison(request: FollowUpInput, media: Sequence[MediaEvidence]) -> bool:
    """Require same-location confirmation and distinct before/after images for visual claims."""
    images = {item.evidence_id for item in media if item.mime_type.startswith("image/")}
    baseline_hashes = {
        sha256(item.content).digest()
        for item in media
        if item.evidence_id in request.baseline_evidence_ids and item.evidence_id in images
    }
    follow_up_hashes = {
        sha256(item.content).digest()
        for item in media
        if item.evidence_id in request.follow_up_evidence_ids and item.evidence_id in images
    }
    return (
        request.same_location_confirmed
        and bool(images.intersection(request.baseline_evidence_ids))
        and bool(images.intersection(request.follow_up_evidence_ids))
        and bool(follow_up_hashes - baseline_hashes)
    )


def validate_follow_up(
    value: FollowUpAssessment, request: FollowUpInput, media: Sequence[MediaEvidence]
) -> FollowUpAssessment:
    """Reject fabricated citations and unsupported resolution claims regardless of provider."""
    value = FollowUpAssessment.model_validate(value)
    known = {item.evidence_id for item in media}
    if not set(value.evidence_ids).issubset(known):
        raise AIError("unsupported_evidence", "Follow-up cites unavailable evidence.")
    if value.outcome != "insufficient_evidence":
        if not sufficient_comparison(request, media):
            raise AIError(
                "unsupported_assessment", "Evidence cannot support a condition assessment."
            )
        images = {item.evidence_id for item in media if item.mime_type.startswith("image/")}
        cited = set(value.evidence_ids) & images
        if not cited.intersection(request.baseline_evidence_ids) or not cited.intersection(
            request.follow_up_evidence_ids
        ):
            raise AIError(
                "unsupported_evidence", "Condition assessment must cite before and after images."
            )
    return value
