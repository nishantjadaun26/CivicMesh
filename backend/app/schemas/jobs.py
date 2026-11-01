"""Schemas for persistent async jobs."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from backend.app.schemas.common import BaseSchema
from civicmesh_ai.integration import FollowUpCompletion, ReportCompletion
from civicmesh_ai.schemas import Clarification, ReviewDecision
from pydantic import Field

JobStatus = Literal["pending", "running", "waiting_for_input", "completed", "failed"]


class PendingAction(BaseSchema):
    interrupt_id: str
    kind: str
    prompt: dict[str, Any]


class JobResponse(BaseSchema):
    job_id: UUID
    report_id: UUID | None
    follow_up_id: UUID | None = None
    status: JobStatus
    attempts: int = 0
    failures: int = 0
    max_attempts: int = 3
    error_code: str | None = None
    error_message: str | None = None
    checkpoint_id: str | None = None
    pending_action: PendingAction | None = None
    result: ReportCompletion | FollowUpCompletion | None = None
    created_at: datetime
    updated_at: datetime


class JobAnswerRequest(BaseSchema):
    checkpoint_id: str = Field(min_length=1, max_length=255)
    interrupt_id: str = Field(min_length=1, max_length=255)
    reply: Clarification | ReviewDecision
