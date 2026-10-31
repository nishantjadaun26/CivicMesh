from typing import Protocol
from uuid import UUID

from app.schemas.contracts import ReportCreate, Submission


class ReportService(Protocol):
    def submit(self, owner_id: UUID, request: ReportCreate, idempotency_key: str) -> Submission:
        """Validate locality/ownership and atomically persist report, evidence bindings and job."""
        ...
