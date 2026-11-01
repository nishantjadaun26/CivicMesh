"""Deterministic provider used only by isolated integration tests, never runtime."""

from civicmesh_ai.assessment import AuthorityRecommendation, ComplaintContent, PriorityAssessment
from civicmesh_ai.schemas import Extraction


class TestProvider:
    __test__ = False

    def __init__(self):
        self.calls = 0
        self.failures = []

    async def extract(self, request, *, media=()):
        self.calls += 1
        if self.failures:
            raise self.failures.pop(0)
        return Extraction(
            category="garbage", summary="Discarded bags cover the pavement.", language="en"
        )

    async def assess_priority(self, extraction):
        return PriorityAssessment(
            level="unknown", rationale="Impact cannot be established from this observation."
        )

    async def recommend_authority(self, extraction, sources):
        return AuthorityRecommendation(
            authority_id=sources[0].authority_id,
            source_ids=[sources[0].document_id],
            rationale="The supplied verified passage identifies the recipient.",
        )

    async def prepare_complaint(self, extraction, recommendation, sources):
        return ComplaintContent(
            subject="Garbage observation",
            observations=[extraction.summary],
            requested_action="Please inspect the reported condition.",
            source_ids=recommendation.source_ids,
        )
