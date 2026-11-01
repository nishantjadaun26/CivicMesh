"""Persistent async jobs queue and idempotent atomic report submission."""

from uuid import UUID, uuid4

from backend.app.core.config import get_settings
from backend.app.core.errors import ConflictError
from backend.app.database.models import Evidence, Job, Profile, Report
from backend.app.schemas.reports import ReportCreateRequest
from backend.app.services.storage.media import StorageService
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

settings = get_settings()


class JobQueueService:
    @staticmethod
    async def validate_replay(report, request, db):
        ids = set((await db.execute(select(Evidence.id).where(Evidence.report_id == report.id))).scalars().all())
        location = request.location
        if (report.text != request.text or report.category != request.category
                or report.latitude != (location.latitude if location else None)
                or report.longitude != (location.longitude if location else None)
                or report.location_confirmed != (location.confirmed if location else False)
                or ids != set(request.evidence_ids)):
            raise ConflictError("Idempotency key was already used for a different report.")

    @staticmethod
    async def create_report_with_job(
        *,
        owner_id: UUID,
        request: ReportCreateRequest,
        idempotency_key: str | None,
        db: AsyncSession,
    ) -> tuple[Report, Job]:
        """Atomically persist report, bind evidence, and enqueue processing job.

        If idempotency_key is provided and already exists for this owner, returns existing report and job.
        """
        if idempotency_key:
            stmt = select(Report).where(
                Report.owner_id == owner_id,
                Report.idempotency_key == idempotency_key,
            )
            result = await db.execute(stmt)
            existing_report = result.scalar_one_or_none()
            if existing_report:
                await JobQueueService.validate_replay(existing_report, request, db)
                job_stmt = (
                    select(Job)
                    .where(Job.report_id == existing_report.id)
                    .order_by(Job.created_at.desc())
                    .limit(1)
                )
                existing_job = (await db.execute(job_stmt)).scalar_one_or_none()
                if existing_job:
                    return existing_report, existing_job

                # Existing report has no job: create one and commit
                new_job = Job(
                    id=uuid4(),
                    owner_id=owner_id,
                    report_id=existing_report.id,
                    kind="report",
                    status="pending",
                    attempts=0,
                    max_attempts=settings.WORKER_MAX_RETRIES,
                )
                db.add(new_job)
                await db.commit()
                await db.refresh(new_job)
                return existing_report, new_job

        # Ensure profile exists for FK constraint (race-safe)
        profile = await db.get(Profile, owner_id)
        if not profile:
            try:
                async with db.begin_nested():
                    db.add(Profile(id=owner_id))
                    await db.flush()
            except IntegrityError:
                # Concurrent insert already created profile
                pass

        report_id = uuid4()
        job_id = uuid4()

        lat = request.location.latitude if request.location else None
        lon = request.location.longitude if request.location else None
        confirmed = request.location.confirmed if request.location else False

        report = Report(
            id=report_id,
            owner_id=owner_id,
            category=request.category,
            text=request.text,
            latitude=lat,
            longitude=lon,
            location_confirmed=confirmed,
            status="pending",
            location=f"SRID=4326;POINT({lon} {lat})" if lat is not None and lon is not None else None,
            idempotency_key=idempotency_key,
        )

        try:
            async with db.begin_nested():
                db.add(report)
                await db.flush()
        except IntegrityError:
            # Concurrent submission with same (owner_id, idempotency_key)
            if idempotency_key:
                stmt = select(Report).where(
                    Report.owner_id == owner_id,
                    Report.idempotency_key == idempotency_key,
                )
                existing_report = (await db.execute(stmt)).scalar_one()
                await JobQueueService.validate_replay(existing_report, request, db)
                job_stmt = (
                    select(Job)
                    .where(Job.report_id == existing_report.id)
                    .order_by(Job.created_at.desc())
                    .limit(1)
                )
                existing_job = (await db.execute(job_stmt)).scalar_one_or_none()
                if existing_job:
                    return existing_report, existing_job
                new_job = Job(
                    id=uuid4(),
                    owner_id=owner_id,
                    report_id=existing_report.id,
                    kind="report",
                    status="pending",
                    attempts=0,
                    max_attempts=settings.WORKER_MAX_RETRIES,
                )
                db.add(new_job)
                await db.commit()
                await db.refresh(new_job)
                return existing_report, new_job
            raise

        # Bind evidence items (flushes within current transaction)
        if request.evidence_ids:
            await StorageService.verify_and_bind_evidence(
                owner_id=owner_id,
                evidence_ids=request.evidence_ids,
                db=db,
                report_id=report_id,
            )

        job = Job(
            id=job_id,
            owner_id=owner_id,
            report_id=report_id,
            kind="report",
            status="pending",
            attempts=0,
            max_attempts=settings.WORKER_MAX_RETRIES,
        )
        db.add(job)

        await db.commit()
        await db.refresh(report)
        await db.refresh(job)
        return report, job
