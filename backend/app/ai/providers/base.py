from collections.abc import Sequence
from typing import Protocol

from civicmesh_ai.assessment import (
    AuthorityRecommendation,
    ComplaintContent,
    FollowUpAssessment,
    FollowUpInput,
    OfficialSource,
    PriorityAssessment,
)
from civicmesh_ai.media import MediaEvidence
from civicmesh_ai.schemas import Extraction, ExtractionRequest


class ExtractionProvider(Protocol):
    """Replaceable extraction implementation, supporting verified private media."""

    async def extract(
        self, request: ExtractionRequest, *, media: Sequence[MediaEvidence] = ()
    ) -> Extraction: ...


class WorkflowProvider(ExtractionProvider, Protocol):
    """Full AI module interface; responses are revalidated by graph nodes."""

    async def assess_priority(self, extraction: Extraction) -> PriorityAssessment: ...
    async def recommend_authority(
        self, extraction: Extraction, sources: list[OfficialSource]
    ) -> AuthorityRecommendation: ...
    async def prepare_complaint(
        self,
        extraction: Extraction,
        recommendation: AuthorityRecommendation,
        sources: list[OfficialSource],
    ) -> ComplaintContent: ...
    async def assess_follow_up(
        self, request: FollowUpInput, *, media: Sequence[MediaEvidence] = ()
    ) -> FollowUpAssessment: ...
