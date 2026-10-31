from typing import Protocol
from uuid import UUID

from civicmesh_ai.schemas import Schema, ShortText
from pydantic import AwareDatetime, HttpUrl


class OfficialSource(Schema):
    document_id: UUID
    url: HttpUrl
    retrieved_at: AwareDatetime
    supporting_passage: ShortText


class BackendTools(Protocol):
    """Backend enforces ownership, locality and official-source verification.

    Identity comes from authenticated worker context, never from model output.
    These interfaces are not yet called by the first extraction milestone.
    """

    async def incident_candidates(self, *, report_id: UUID, owner_id: UUID) -> list[UUID]: ...
    async def authority_sources(
        self, *, report_id: UUID, owner_id: UUID
    ) -> list[OfficialSource]: ...
