"""Expose shared schemas for API and backend services."""

from backend.app.schemas.common import (
    BaseSchema,
    Category,
    ConfirmedLocation,
    PaginationMeta,
    PaginationParams,
)
from backend.app.schemas.incidents import (
    FollowUpCreateRequest,
    FollowUpResponse,
    IncidentDetailResponse,
    IncidentPublicResponse,
    StatusEventResponse,
)
from backend.app.schemas.jobs import (
    JobResponse,
    JobStatus,
    PendingAction,
)
from backend.app.schemas.reports import (
    ClarificationAnswerRequest,
    ReportCreateRequest,
    ReportDetailResponse,
    ReportResponse,
)
from backend.app.schemas.uploads import (
    EvidenceResponse,
    UploadPrepareRequest,
    UploadPrepareResponse,
)

__all__ = [
    "BaseSchema",
    "Category",
    "ConfirmedLocation",
    "PaginationMeta",
    "PaginationParams",
    "UploadPrepareRequest",
    "UploadPrepareResponse",
    "EvidenceResponse",
    "ReportCreateRequest",
    "ReportResponse",
    "ReportDetailResponse",
    "ClarificationAnswerRequest",
    "JobStatus",
    "JobResponse",
    "PendingAction",
    "IncidentPublicResponse",
    "IncidentDetailResponse",
    "FollowUpCreateRequest",
    "FollowUpResponse",
    "StatusEventResponse",
]
