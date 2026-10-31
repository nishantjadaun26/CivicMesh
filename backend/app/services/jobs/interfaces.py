from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class ClaimedJob:
    job_id: UUID
    owner_id: UUID
    lease_token: UUID
    attempts: int
    lease_expires_at: datetime


class JobStore(Protocol):
    """Claim atomically with FOR UPDATE SKIP LOCKED; fence updates by lease token.

    Reclaim expired leases only below max_attempts. Persist retry times; classify
    permanent vs transient errors. Side effects require stable idempotency keys.
    """

    def claim(self, worker_id: str) -> ClaimedJob | None: ...
    def heartbeat(self, job: ClaimedJob) -> None: ...
    def succeed(self, job: ClaimedJob) -> None: ...
    def fail(self, job: ClaimedJob, error_code: str, retry_at: datetime | None) -> None: ...
