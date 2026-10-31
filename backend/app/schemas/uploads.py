"""Schemas for authenticated private media uploads."""

from datetime import datetime
from uuid import UUID

from backend.app.schemas.common import BaseSchema
from pydantic import Field, field_validator

# Allowed MIME types for citizen evidence
ALLOWED_MIME_TYPES = {
    # Images
    "image/jpeg",
    "image/png",
    "image/webp",
    # Audio
    "audio/webm",
    "audio/ogg",
    "audio/mp4",
    "audio/wav",
    "audio/mpeg",
}

# Max file size limits (15MB for images, 10MB for audio)
MAX_IMAGE_SIZE_BYTES = 15 * 1024 * 1024
MAX_AUDIO_SIZE_BYTES = 10 * 1024 * 1024


class UploadPrepareRequest(BaseSchema):
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=3, max_length=100)
    file_size_bytes: int = Field(gt=0)

    @field_validator("content_type")
    @classmethod
    def validate_content_type(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in ALLOWED_MIME_TYPES:
            raise ValueError(
                f"Unsupported media type: {value}. Allowed: {sorted(ALLOWED_MIME_TYPES)}"
            )
        return normalized

    @field_validator("file_size_bytes")
    @classmethod
    def validate_file_size(cls, value: int, info) -> int:
        content_type = info.data.get("content_type", "")
        if content_type.startswith("image/") and value > MAX_IMAGE_SIZE_BYTES:
            raise ValueError(f"Image file size exceeds limit of {MAX_IMAGE_SIZE_BYTES // (1024*1024)}MB")
        if content_type.startswith("audio/") and value > MAX_AUDIO_SIZE_BYTES:
            raise ValueError(f"Audio file size exceeds limit of {MAX_AUDIO_SIZE_BYTES // (1024*1024)}MB")
        return value


class UploadPrepareResponse(BaseSchema):
    evidence_id: UUID
    upload_url: str
    storage_path: str
    expires_in_seconds: int = 3600


class EvidenceResponse(BaseSchema):
    id: UUID
    owner_id: UUID
    mime_type: str
    file_size_bytes: int
    verified: bool
    created_at: datetime
