from typing import Protocol
from uuid import UUID

from app.schemas.contracts import Incident


class IncidentService(Protocol):
    def get_approved(self, incident_id: UUID) -> Incident | None: ...
    def reverse_membership(self, membership_id: UUID, actor_id: UUID, reason: str) -> None: ...
