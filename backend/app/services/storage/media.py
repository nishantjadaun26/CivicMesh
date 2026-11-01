"""Private storage media handling and evidence verification."""

import logging
from uuid import UUID, uuid4

import httpx
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

logger = logging.getLogger("civicmesh.storage")
settings = get_settings()

MIME_EXTENSION_MAP: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "audio/mp4": ".m4a",
    "audio/mpeg": ".mp3",
    "audio/wav": ".wav",
}


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
        ext = MIME_EXTENSION_MAP.get(request.content_type, ".bin")
        safe_filename = f"{uuid4().hex}{ext}"
        storage_path = f"evidence/{owner_id}/{evidence_id}/{safe_filename}"

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

        # Request signed expiring upload URL from Storage API if service role is configured
        upload_url = None
        expires_in = 3600
        if not any(p in settings.SUPABASE_SERVICE_ROLE_KEY.lower() for p in ["placeholder", "dev-"]):
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    sign_url = (
                        f"{settings.SUPABASE_URL.rstrip('/')}/storage/v1/object/upload/sign/"
                        f"{settings.STORAGE_EVIDENCE_BUCKET}/{storage_path}"
                    )
                    resp = await client.post(
                        sign_url,
                        headers={"Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}"},
                        json={"expiresIn": expires_in},
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        if data.get("url"):
                            rel_url = data["url"]
                            if rel_url.startswith("http://") or rel_url.startswith("https://"):
                                upload_url = rel_url
                            elif rel_url.startswith("/storage/v1"):
                                upload_url = f"{settings.SUPABASE_URL.rstrip('/')}{rel_url}"
                            elif rel_url.startswith("/"):
                                upload_url = f"{settings.SUPABASE_URL.rstrip('/')}/storage/v1{rel_url}"
                            else:
                                upload_url = f"{settings.SUPABASE_URL.rstrip('/')}/storage/v1/{rel_url}"
                        elif data.get("token"):
                            token = data["token"]
                            upload_url = (
                                f"{settings.SUPABASE_URL.rstrip('/')}/storage/v1/object/upload/sign/"
                                f"{settings.STORAGE_EVIDENCE_BUCKET}/{storage_path}?token={token}"
                            )
                    else:
                        logger.warning(
                            "Supabase storage signing returned non-200 status: %d",
                            resp.status_code,
                        )
            except Exception as exc:
                logger.warning("Supabase storage signing failed: %s", type(exc).__name__)

        if not upload_url:
            upload_url = (
                f"{settings.SUPABASE_URL.rstrip('/')}/storage/v1/object/"
                f"{settings.STORAGE_EVIDENCE_BUCKET}/{storage_path}"
            )

        return UploadPrepareResponse(
            evidence_id=evidence_id,
            upload_url=upload_url,
            storage_path=storage_path,
            expires_in_seconds=expires_in,
        )

    @staticmethod
    async def verify_and_bind_evidence(
        owner_id: UUID,
        evidence_ids: list[UUID],
        db: AsyncSession,
        report_id: UUID | None = None,
        incident_id: UUID | None = None,
    ) -> list[Evidence]:
        """Verify ownership and bind evidence items to report and/or incident.

        Flushes changes rather than committing so the caller can control transaction atomicity.
        """
        if not evidence_ids:
            return []

        if report_id is None and incident_id is None:
            raise ValidationError("Evidence must be bound to a report or an incident.")

        query = select(Evidence).where(Evidence.id.in_(evidence_ids)).with_for_update()
        result = await db.execute(query)
        items = list(result.scalars().all())

        if len(items) != len(evidence_ids):
            found_ids = {e.id for e in items}
            missing = set(evidence_ids) - found_ids
            raise NotFoundError(f"Evidence item(s) not found: {missing}")

        for item in items:
            if item.owner_id != owner_id:
                raise ForbiddenError(f"Evidence item {item.id} is not owned by the authenticated citizen.")

            # Reject if already bound to another report or another incident
            if report_id is not None and item.report_id is not None and item.report_id != report_id:
                raise ValidationError(f"Evidence item {item.id} is already bound to report {item.report_id}.")
            if incident_id is not None and item.incident_id is not None and item.incident_id != incident_id:
                raise ValidationError(f"Evidence item {item.id} is already bound to incident {item.incident_id}.")

            if report_id is not None:
                item.report_id = report_id
            if incident_id is not None:
                item.incident_id = incident_id

        # Flush to register bindings in session without prematurely committing caller's transaction
        await db.flush()
        return items
