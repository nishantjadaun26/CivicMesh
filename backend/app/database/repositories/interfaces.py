from typing import Protocol
from uuid import UUID

from app.schemas.contracts import IncidentPage, Report, ReportCreate, Submission


class ReportRepository(Protocol):
    def get_owned(self, report_id: UUID, owner_id: UUID) -> Report | None: ...
    def submit_with_job(
        self, owner_id: UUID, request: ReportCreate, idempotency_key: str
    ) -> Submission: ...


class IncidentRepository(Protocol):
    def list_approved(self, limit: int, cursor: str | None) -> IncidentPage: ...
    def unlink_report(self, membership_id: UUID, actor_id: UUID, reason: str) -> None: ...
