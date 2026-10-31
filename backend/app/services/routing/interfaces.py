from typing import Protocol
from uuid import UUID


class RoutingService(Protocol):
    def verified_source_ids(self, report_id: UUID, owner_id: UUID) -> list[UUID]:
        """Only verified official sources for the selected locality, with supporting passages."""
        ...
