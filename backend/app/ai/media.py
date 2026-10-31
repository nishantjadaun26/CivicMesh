"""Bounded, private inline media. Never fetch URLs or checkpoint raw media bytes."""

from collections.abc import Sequence
from typing import Literal
from uuid import UUID

from civicmesh_ai.errors import AIError
from civicmesh_ai.schemas import Schema
from pydantic import Field, model_validator

MAX_INLINE_BYTES = 12 * 1024 * 1024  # Leaves headroom for base64 and JSON overhead.
MediaType = Literal[
    "image/jpeg",
    "image/png",
    "image/webp",
    "audio/webm",
    "audio/ogg",
    "audio/mp4",
    "audio/mpeg",
    "audio/wav",
]


class MediaEvidence(Schema):
    """Bytes supplied by the authorized storage adapter, never a model-controlled URL."""

    evidence_id: UUID
    mime_type: MediaType
    content: bytes = Field(
        min_length=1, max_length=20 * 1024 * 1024, repr=False, exclude=True, strict=True
    )

    @model_validator(mode="after")
    def check_signature(self):
        """Reject obvious MIME spoofing; full decode/malware checks remain storage-owned."""
        data = self.content
        signatures = {
            "image/jpeg": data.startswith(b"\xff\xd8\xff"),
            "image/png": data.startswith(b"\x89PNG\r\n\x1a\n"),
            "image/webp": data[:4] == b"RIFF" and data[8:12] == b"WEBP",
            "audio/webm": data.startswith(b"\x1aE\xdf\xa3"),
            "audio/ogg": data.startswith(b"OggS"),
            "audio/mp4": data[4:8] == b"ftyp",
            "audio/mpeg": data.startswith(b"ID3")
            or (len(data) >= 2 and data[0] == 255 and data[1] & 224 == 224),
            "audio/wav": data[:4] == b"RIFF" and data[8:12] == b"WAVE",
        }
        if not signatures[self.mime_type]:
            raise ValueError("Media signature does not match the declared type")
        if self.mime_type.startswith("image/") and len(data) > 10 * 1024 * 1024:
            raise ValueError("Images must not exceed 10 MiB")
        return self


def validate_media(
    media: Sequence[MediaEvidence], expected_ids: Sequence[UUID]
) -> list[MediaEvidence]:
    """Require an exact, unique evidence binding and a bounded inline request size."""
    if len(media) > 10:
        raise AIError("evidence_mismatch", "Use at most 10 attachments.")
    parsed = [MediaEvidence.model_validate(item) for item in media]
    ids = [item.evidence_id for item in parsed]
    if (
        len(ids) > 10
        or len(ids) != len(set(ids))
        or len(expected_ids) != len(set(expected_ids))
        or set(ids) != set(expected_ids)
    ):
        raise AIError("evidence_mismatch", "Media must match the requested evidence identifiers.")
    if sum(len(item.content) for item in parsed) > MAX_INLINE_BYTES:
        raise AIError(
            "media_too_large", "Combined inline media exceeds 12 MiB; reduce attachments."
        )
    return parsed


async def load_media(
    tools,
    *,
    owner_id: UUID,
    report_id: UUID | None,
    incident_id: UUID | None,
    evidence_ids: list[UUID],
) -> list[MediaEvidence]:
    """Resolve private evidence only through a backend adapter with verified user context."""
    if not evidence_ids:
        return []
    if tools is None:
        raise AIError("tools_not_configured", "Private evidence storage adapter is required.")
    media = await tools.load_evidence(
        owner_id=owner_id, report_id=report_id, incident_id=incident_id, evidence_ids=evidence_ids
    )
    return validate_media(media, evidence_ids)
