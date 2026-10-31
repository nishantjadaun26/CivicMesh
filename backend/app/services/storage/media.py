"""Private storage media handling and evidence verification."""

from uuid import UUID, uuid4

from backend.app.core.config import get_settings
from backend.app.core.errors import ForbiddenError, NotFoundError, ValidationError
from backend.app.database.models import Evidence
from backend.app.schemas.uploads import (
    ALLOWED_MIME_TYPES,
    MAX_AUDIO_SIZE_BYTES,
    MAX_IMAGE_SIZE_BYTES,
    UploadPrepareRequest,
    UploadPrepareResponse,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

settings = get_settings()


class StorageService:
    @staticmethod
    async def prepare_upload(
        owner_id: UUID,
        request: UploadPrepareRequest,
        db: AsyncSession,
    ) -> UploadPrepareResponse:
        """Create an owner-bound unverified evidence record and return private upload destination."""
        # Backend validation of MIME and size
        if request.content_type not in ALLOWED_MIME_TYPES:
            raise ValidationError(f"MIME type '{request.content_type}' is not supported.")

        if request.content_type.startswith("image/") and request.file_size_bytes > MAX_IMAGE_SIZE_BYTES:
            raise ValidationError("Image exceeds size limit.")
        if request.content_type.startswith("audio/") and request.file_size_bytes > MAX_AUDIO_SIZE_BYTES:
            raise ValidationError("Audio exceeds size limit.")

        evidence_id = uuid4()
        storage_path = f"evidence/{owner_id}/{evidence_id}/{request.filename}"

        evidence = Evidence(
            id=evidence_id,
            owner_id=owner_id,
            storage_bucket=settings.STORAGE_EVIDENCE_BUCKET,
            storage_path=storage_path,
            mime_type=request.content_type,
            file_size_bytes=request.file_size_bytes,
            verified=False,
        )
        db.add(evidence)
        await db.commit()

        # Upload destination (Presigned Supabase Storage URL or application upload target)
        upload_url = f"{settings.SUPABASE_URL}/storage/v1/object/{settings.STORAGE_EVIDENCE_BUCKET}/{storage_path}"

        return UploadPrepareResponse(
            evidence_id=evidence_id,
            upload_url=upload_url,
            storage_path=storage_path,
            expires_in_seconds=3600,
        )

    @staticmethod
    async def verify_and_bind_evidence(
        owner_id: UUID,
        evidence_ids: list[UUID],
        report_id: UUID,
        db: AsyncSession,
    ) -> list[Evidence]:
        """Verify ownership and bind evidence items to the given report."""
        if not evidence_ids:
            return []

        query = select(Evidence).where(Evidence.id.in_(evidence_ids))
        result = await db.execute(query)
        items = list(result.scalars().all())

        if len(items) != len(evidence_ids):
            found_ids = {e.id for e in items}
            missing = set(evidence_ids) - found_ids
            raise NotFoundError(f"Evidence item(s) not found: {missing}")

        for item in items:
            if item.owner_id != owner_id:
                raise ForbiddenError(f"Evidence item {item.id} is not owned by the authenticated citizen.")
            if item.report_id is not None and item.report_id != report_id:
                raise ValidationError(f"Evidence item {item.id} is already bound to report {item.report_id}.")

            item.report_id = report_id
            item.verified = True

        await db.commit()
        return items
