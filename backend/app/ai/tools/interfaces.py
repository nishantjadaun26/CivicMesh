from typing import Protocol

from app.schemas.contracts import Extraction


class BackendTools(Protocol):
    """Implementations enforce ownership, locality and verified source allowlists.

    Model text cannot choose arbitrary URLs, SQL, tool permissions or user IDs.
    """

    async def find_candidates(self, report_id: str, owner_id: str) -> list[str]: ...
    async def lookup_authority(self, report_id: str, owner_id: str) -> list[str]: ...


class ExtractionProvider(Protocol):
    async def extract(self, text: str) -> Extraction: ...
