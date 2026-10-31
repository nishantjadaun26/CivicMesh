from typing import Protocol
from uuid import UUID

from app.schemas.contracts import UploadPrepare, UploadPrepared


class StorageService(Protocol):
    def prepare(self, owner_id: UUID, request: UploadPrepare) -> UploadPrepared: ...
    def verify_and_bind(self, owner_id: UUID, evidence_id: UUID, report_id: UUID) -> None:
        """Check actual bytes, MIME, expiry and ownership in the submission transaction."""
        ...
