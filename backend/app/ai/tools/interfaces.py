"""Contracts implemented by the backend teammate, not by model-generated tool calls."""

from typing import Protocol
from uuid import UUID

from civicmesh_ai.assessment import IncidentCandidate, OfficialSource
from civicmesh_ai.media import MediaEvidence
from civicmesh_ai.schemas import Category, ConfirmedLocation


class BackendTools(Protocol):
    """Adapters enforce ownership, evidence binding, locality and source verification.

    Owner IDs come from authenticated worker context. Arbitrary citizen URLs, model
    instructions and unverified identity values must never control these adapters.
    """

    async def load_evidence(
        self,
        *,
        owner_id: UUID,
        report_id: UUID | None,
        incident_id: UUID | None,
        evidence_ids: list[UUID],
    ) -> list[MediaEvidence]:
        """Read only validated private objects bound to the specified report/incident."""
        ...

    async def incident_candidates(
        self, *, report_id: UUID, owner_id: UUID, category: Category, location: ConfirmedLocation
    ) -> list[IncidentCandidate]:
        """Suggest at most 20 candidates using location, category, time and similarity."""
        ...

    async def authority_sources(
        self, *, report_id: UUID, owner_id: UUID, category: Category, location: ConfirmedLocation
    ) -> list[OfficialSource]:
        """Return at most 10 verified official passages for the report's locality."""
        ...
