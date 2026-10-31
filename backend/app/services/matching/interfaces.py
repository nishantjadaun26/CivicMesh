from typing import Protocol
from uuid import UUID


class MatchingService(Protocol):
    def candidates(self, report_id: UUID, owner_id: UUID) -> list[UUID]:
        """Use category, metre distance, time and similarity. Suggest; never silently merge."""
        ...
