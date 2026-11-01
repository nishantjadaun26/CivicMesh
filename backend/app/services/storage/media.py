"""Private storage media handling and evidence verification."""

from hashlib import sha256
from urllib.parse import quote, urljoin, urlsplit
from uuid import UUID, uuid4

import httpx
from backend.app.core.config import PLACEHOLDERS, get_settings
from backend.app.core.errors import (
    ForbiddenError,
    NotFoundError,
    ServiceUnavailableError,
    ValidationError,
)
from backend.app.database.models import Evidence, Profile
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

MIME_EXTENSION_MAP: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "audio/webm": ".webm",
    "audio/ogg": ".ogg",
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

        key = settings.SUPABASE_SERVICE_ROLE_KEY
        if not key or any(value in key.lower() for value in PLACEHOLDERS):
            raise ServiceUnavailableError("Private storage signing is not configured.")

        evidence_id = uuid4()
        ext = MIME_EXTENSION_MAP.get(request.content_type, ".bin")
        storage_path = f"evidence/{owner_id}/{evidence_id}/{uuid4().hex}{ext}"
        base = settings.SUPABASE_URL.rstrip("/")
        sign_url = f"{base}/storage/v1/object/upload/sign/{settings.STORAGE_EVIDENCE_BUCKET}/{storage_path}"
        try:
            async with httpx.AsyncClient(timeout=10, follow_redirects=False, trust_env=False) as client:
                response = await client.post(sign_url,
                    headers={"Authorization": f"Bearer {key}", "apikey": key}, json={"upsert": False})
            response.raise_for_status()
            data = response.json()
            if data.get("url"):
                path = data["url"]
                upload_url = urljoin(f"{base}/storage/v1/", path.lstrip("/") if not path.startswith("/storage/v1/") else path)
            elif data.get("token"):
                upload_url = f"{sign_url}?token={quote(data['token'], safe='')}"
            else:
                raise ValueError("No signed destination")
            parsed, project = urlsplit(upload_url), urlsplit(base)
            if (parsed.scheme != "https" or parsed.netloc != project.netloc
                    or not parsed.path.startswith("/storage/v1/object/upload/sign/")
                    or not parsed.query):
                raise ValueError("Invalid signed destination")
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            raise ServiceUnavailableError("Private storage could not prepare an upload.") from None

        if await db.get(Profile, owner_id) is None:
            from sqlalchemy.exc import IntegrityError
            try:
                async with db.begin_nested():
                    db.add(Profile(id=owner_id))
                    await db.flush()
            except IntegrityError:
                pass
        evidence = Evidence(id=evidence_id, owner_id=owner_id,
            storage_bucket=settings.STORAGE_EVIDENCE_BUCKET, storage_path=storage_path,
            mime_type=request.content_type, file_size_bytes=request.file_size_bytes, verified=False)
        db.add(evidence)
        await db.commit()
        return UploadPrepareResponse(evidence_id=evidence_id, upload_url=upload_url,
            storage_path=storage_path, expires_in_seconds=7200)

    @staticmethod
    async def verify_uploaded_object(item: Evidence) -> bytes:
        """Verify actual bounded object bytes before marking owner media as bindable."""
        key = settings.SUPABASE_SERVICE_ROLE_KEY
        if not key or any(value in key.lower() for value in PLACEHOLDERS):
            raise ServiceUnavailableError("Private storage verification is not configured.")
        url = (f"{settings.SUPABASE_URL.rstrip('/')}/storage/v1/object/authenticated/"
               f"{quote(item.storage_bucket, safe='')}/{quote(item.storage_path, safe='/')}")
        limit = MAX_IMAGE_SIZE_BYTES if item.mime_type.startswith("image/") else MAX_AUDIO_SIZE_BYTES
        try:
            async with httpx.AsyncClient(timeout=10, follow_redirects=False, trust_env=False) as client:
                async with client.stream("GET", url, headers={"Authorization": f"Bearer {key}", "apikey": key}) as response:
                    if response.status_code == 404:
                        raise ValidationError("Evidence upload is not complete.")
                    response.raise_for_status()
                    if response.headers.get("content-type", "").split(";")[0].strip() != item.mime_type:
                        raise ValidationError("Stored evidence MIME type does not match its ticket.")
                    chunks, size = [], 0
                    async for chunk in response.aiter_bytes():
                        size += len(chunk)
                        if size > limit:
                            raise ValidationError("Stored evidence exceeds its size limit.")
                        chunks.append(chunk)
        except httpx.HTTPError:
            raise ServiceUnavailableError("Private storage verification is unavailable.") from None
        content = b"".join(chunks)
        if len(content) != item.file_size_bytes:
            raise ValidationError("Stored evidence size does not match its ticket.")
        signatures = {
            "image/jpeg": content.startswith(b"\xff\xd8\xff"),
            "image/png": content.startswith(b"\x89PNG\r\n\x1a\n"),
            "image/webp": content[:4] == b"RIFF" and content[8:12] == b"WEBP",
            "audio/webm": content.startswith(b"\x1aE\xdf\xa3"),
            "audio/ogg": content.startswith(b"OggS"),
            "audio/mp4": content[4:8] == b"ftyp",
            "audio/wav": content[:4] == b"RIFF" and content[8:12] == b"WAVE",
            "audio/mpeg": content.startswith(b"ID3") or (len(content) >= 2 and content[0] == 255 and content[1] & 224 == 224),
        }
        if not signatures.get(item.mime_type, False):
            raise ValidationError("Stored evidence signature does not match its MIME type.")
        digest = sha256(content).hexdigest()
        if item.sha256_hash and item.sha256_hash != digest:
            raise ValidationError("Stored evidence changed after verification.")
        item.sha256_hash, item.verified = digest, True
        return content

    @staticmethod
    async def verify_and_bind_evidence(
        owner_id: UUID,
        evidence_ids: list[UUID],
        db: AsyncSession,
        report_id: UUID | None = None,
        incident_id: UUID | None = None,
        follow_up_id: UUID | None = None,
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
            if follow_up_id is not None and (item.report_id is not None or item.follow_up_id is not None):
                raise ValidationError("Follow-up evidence must be a fresh upload.")
            if report_id is not None and item.follow_up_id is not None:
                raise ValidationError("Report evidence cannot already belong to a follow-up.")

        if sum(item.file_size_bytes for item in items) > 12 * 1024 * 1024:
            raise ValidationError("Combined AI evidence must not exceed 12 MiB.")

        for item in items:
            await StorageService.verify_uploaded_object(item)

            if report_id is not None:
                item.report_id = report_id
            if incident_id is not None:
                item.incident_id = incident_id
            if follow_up_id is not None:
                item.follow_up_id = follow_up_id

        # Flush to register bindings in session without prematurely committing caller's transaction
        await db.flush()
        return items
