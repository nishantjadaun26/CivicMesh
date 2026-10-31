"""Binary header fixtures exist only for validation tests, not operational data."""

from uuid import UUID

import pytest
from civicmesh_ai.errors import AIError
from civicmesh_ai.media import MediaEvidence, validate_media
from pydantic import ValidationError


@pytest.mark.parametrize(
    "mime,data",
    [
        ("image/jpeg", b"\xff\xd8\xff\x00"),
        ("image/png", b"\x89PNG\r\n\x1a\n"),
        ("image/webp", b"RIFF0000WEBP"),
        ("audio/webm", b"\x1aE\xdf\xa3"),
        ("audio/ogg", b"OggS"),
        ("audio/mp4", b"0000ftyp"),
        ("audio/mpeg", b"ID3"),
        ("audio/wav", b"RIFF0000WAVE"),
    ],
)
def test_supported_media_headers(mime, data):
    """Every configured media format accepts its expected signature without leaking bytes."""
    item = MediaEvidence(evidence_id=UUID(int=1), mime_type=mime, content=data)
    assert validate_media([item], [item.evidence_id]) == [item]
    assert "content" not in item.model_dump()
    assert "content=" not in repr(item)


def test_spoofed_oversized_and_mismatched_media_fail_closed():
    """Reject MIME spoofing, excess inline data and unexpected storage object bindings."""
    with pytest.raises(ValidationError):
        MediaEvidence(evidence_id=UUID(int=1), mime_type="image/png", content=b"<script/>")
    with pytest.raises(ValidationError):
        MediaEvidence(
            evidence_id=UUID(int=1),
            mime_type="image/jpeg",
            content=b"\xff\xd8\xff" + b"x" * (10 * 1024 * 1024),
        )
    first = MediaEvidence(
        evidence_id=UUID(int=1), mime_type="audio/mpeg", content=b"ID3" + b"x" * (7 * 1024 * 1024)
    )
    second = MediaEvidence(evidence_id=UUID(int=2), mime_type="audio/mpeg", content=first.content)
    with pytest.raises(AIError, match="12 MiB"):
        validate_media([first, second], [first.evidence_id, second.evidence_id])
    with pytest.raises(AIError, match="identifiers"):
        validate_media([first], [UUID(int=3)])
    with pytest.raises(AIError, match="identifiers"):
        validate_media([first, first], [first.evidence_id])
