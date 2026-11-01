"""Persistent, bounded AI job execution with crash recovery and human review."""

import asyncio
import logging
from datetime import timedelta
from uuid import uuid4

from backend.app.core.errors import ServiceUnavailableError
from backend.app.database.models import (
    Evidence,
    FollowUp,
    Incident,
    IncidentReport,
    Job,
    Report,
    WorkerHeartbeat,
    WorkflowRun,
    utc_now,
)
from backend.app.worker.locks import HeldWorkflowLock, JobLocks
from backend.app.worker.tools import BackendToolsAdapter
from civicmesh_ai.assessment import FollowUpInput
from civicmesh_ai.coordinator import WorkflowCoordinator
from civicmesh_ai.errors import AIError
from civicmesh_ai.schemas import ConfirmedLocation, Extraction, ReportInput
from psycopg import InterfaceError, OperationalError
from sqlalchemy import and_, or_, select

logger = logging.getLogger("civicmesh.worker")


class Worker:
    def __init__(self, *, sessions, engine, provider, saver, settings):
        self.sessions, self.provider, self.saver, self.settings = (
            sessions,
            provider,
            saver,
            settings,
        )
        self.locks = JobLocks(engine)
        self.worker_id = str(uuid4())

    async def heartbeat(self):
        # Readiness must not stay fresh when private checkpoint storage is down.
        await self.saver.aget_tuple({"configurable": {"thread_id": "civicmesh:health"}})
        async with self.sessions() as db:
            row = await db.get(WorkerHeartbeat, self.worker_id)
            if row is None:
                row = WorkerHeartbeat(worker_id=self.worker_id)
                db.add(row)
            row.last_seen = utc_now()
            # Old workers are not evidence of present readiness.
            from sqlalchemy import delete

            await db.execute(
                delete(WorkerHeartbeat).where(
                    WorkerHeartbeat.last_seen < utc_now() - timedelta(days=1)
                )
            )
            await db.commit()

    def eligible(self):
        now = utc_now()
        return or_(
            and_(Job.status == "pending", Job.available_at <= now),
            and_(
                Job.status == "running",
                Job.locked_at < now - timedelta(seconds=self.settings.WORKER_LEASE_SECONDS),
            ),
        )

    async def run_once(self, *, limit: int = 20):
        """Process up to ``limit`` eligible jobs, then return to the caller."""
        if not 1 <= limit <= 20:
            raise ValueError("Worker job limit must be between 1 and 20")
        async with self.sessions() as db:
            ids = list(
                (
                    await db.execute(
                        select(Job.id)
                        .where(self.eligible())
                        .order_by(Job.available_at, Job.created_at)
                        .limit(limit)
                    )
                ).scalars()
            )
        for job_id in ids:
            async with self.locks.try_hold(job_id) as acquired:
                if not acquired:
                    continue
                async with self.sessions() as db:
                    job = (
                        await db.execute(
                            select(Job).where(Job.id == job_id, self.eligible()).with_for_update()
                        )
                    ).scalar_one_or_none()
                    if job is None:
                        continue
                    if job.status == "running":
                        job.failures += (
                            1  # A crashed/timed-out attempt consumes the same durable budget.
                        )
                    target = (
                        await db.get(Report, job.report_id)
                        if job.report_id
                        else await db.get(FollowUp, job.follow_up_id)
                    )
                    if job.failures >= job.max_attempts:
                        job.status = target.status = "failed"
                        job.error_code, job.error_message = (
                            "retry_budget_exhausted",
                            "Processing stopped after repeated failures.",
                        )
                        job.locked_at = job.locked_by = None
                        await db.commit()
                        return True
                    job.status, target.status = "running", "processing"
                    job.locked_at, job.locked_by = utc_now(), self.worker_id
                    job.attempts += 1
                    await db.commit()
                    try:
                        async with asyncio.timeout(self.settings.WORKER_JOB_TIMEOUT_SECONDS):
                            await self.process(db, job, target)
                    except Exception as error:
                        # No model output, citizen text, DSNs, object tokens or provider messages in logs.
                        logger.warning("Job failed id=%s type=%s", job_id, type(error).__name__)
                        await db.rollback()
                        job = await db.get(Job, job_id)
                        target = (
                            await db.get(Report, job.report_id)
                            if job.report_id
                            else await db.get(FollowUp, job.follow_up_id)
                        )
                        retryable = (isinstance(error, AIError) and error.retryable) or isinstance(
                            error,
                            (
                                ServiceUnavailableError,
                                TimeoutError,
                                ConnectionError,
                                OperationalError,
                                InterfaceError,
                            ),
                        )
                        job.failures += 1
                        job.error_code = (
                            error.code if isinstance(error, AIError) else "processing_unavailable"
                        )
                        job.error_message = (
                            "Processing is temporarily unavailable."
                            if retryable
                            else "Processing could not complete. Please contact the project owner."
                        )
                        job.status = (
                            "pending" if retryable and job.failures < job.max_attempts else "failed"
                        )
                        target.status = "pending" if job.status == "pending" else "failed"
                        job.available_at = utc_now() + timedelta(
                            seconds=min(300, 5 * 2**job.failures)
                        )
                        job.locked_at = job.locked_by = None
                        await db.commit()
                    return True
        return False

    async def process(self, db, job, target):
        tools = BackendToolsAdapter(db, follow_up_id=job.follow_up_id, settings=self.settings)
        coordinator = WorkflowCoordinator(
            self.provider, tools=tools, checkpointer=self.saver, locks=HeldWorkflowLock(job.id)
        )
        try:
            view = await coordinator.inspect(job.id, owner_id=job.owner_id)
        except AIError as error:
            if error.code != "workflow_not_found":
                raise
            if job.checkpoint_id is not None or (job.pending_action or {}).get("resume_pending"):
                raise AIError(
                    "checkpoint_unavailable",
                    "Saved workflow state is unavailable; operator recovery is required.",
                ) from None
            if job.report_id:
                ids = list(
                    (
                        await db.execute(select(Evidence.id).where(Evidence.report_id == target.id))
                    ).scalars()
                )
                location = (
                    ConfirmedLocation(
                        latitude=target.latitude, longitude=target.longitude, confirmed=True
                    )
                    if target.location_confirmed
                    else None
                )
                report = ReportInput(
                    report_id=target.id,
                    text=target.text,
                    evidence_ids=ids,
                    category=target.category,
                    location=location,
                )
                view = await coordinator.start_report(job.id, owner_id=job.owner_id, report=report)
            else:
                request = await self.follow_up_input(db, job, target)
                view = await coordinator.start_follow_up(
                    job.id, owner_id=job.owner_id, request=request
                )
        else:
            action = job.pending_action or {}
            if (
                view.status == "waiting_for_input"
                and action.get("resume_pending")
                and view.checkpoint_id == job.checkpoint_id
            ):
                view = await coordinator.resume(
                    job.id,
                    owner_id=job.owner_id,
                    checkpoint_id=job.checkpoint_id,
                    interrupt_id=action["interrupt_id"],
                    reply=action["reply"],
                )
            elif view.status == "incomplete":
                view = await coordinator.retry(
                    job.id, owner_id=job.owner_id, checkpoint_id=view.checkpoint_id
                )
            # A newer checkpoint after a crash is authoritative. Never replay an old approval.
        if view.status == "incomplete":
            raise AIError(
                "workflow_incomplete",
                "Processing did not reach a persisted outcome.",
                retryable=True,
            )
        job.checkpoint_id = view.checkpoint_id
        job.error_code = job.error_message = None
        job.locked_at = job.locked_by = None
        if view.status == "waiting_for_input":
            action = view.pending[0]
            job.pending_action = {
                "kind": action.kind,
                "interrupt_id": action.interrupt_id,
                "prompt": action.payload,
            }
            job.status = target.status = "waiting_for_input"
        else:
            job.pending_action = None
            job.status, target.status = "completed", "processed"
            if job.report_id:
                target.extraction_result = view.output.model_dump(mode="json")
            else:
                target.result = view.output.model_dump(mode="json")
        run = await db.get(WorkflowRun, job.id)
        if run is None:
            run = WorkflowRun(id=job.id, job_id=job.id, workflow_id=job.id, owner_id=job.owner_id)
            db.add(run)
        run.state = view.status
        run.result_payload = view.output.model_dump(mode="json") if view.output else None
        await db.commit()

    async def follow_up_input(self, db, job, target):
        incident = await db.get(Incident, target.incident_id)
        if incident is None or not incident.is_public:
            raise AIError("incident_unavailable", "The public incident is no longer available.")
        current_rows = (
            await db.execute(
                select(Evidence.id, Evidence.file_size_bytes).where(
                    Evidence.follow_up_id == target.id
                )
            )
        ).all()
        current = [identifier for identifier, _ in current_rows]
        remaining = 12 * 1024 * 1024 - sum(size for _, size in current_rows)
        # Baselines remain private: another citizen's original photo is never disclosed to this workflow.
        baseline_rows = list(
            (
                await db.execute(
                    select(Evidence.id, Evidence.file_size_bytes)
                    .join(IncidentReport, Evidence.report_id == IncidentReport.report_id)
                    .where(
                        IncidentReport.incident_id == target.incident_id,
                        IncidentReport.is_active.is_(True),
                        Evidence.owner_id == job.owner_id,
                        Evidence.verified.is_(True),
                        Evidence.mime_type.like("image/%"),
                    )
                    .order_by(Evidence.created_at)
                    .limit(5)
                )
            ).all()
        )
        baseline = []
        for identifier, size in baseline_rows:
            if size <= remaining:
                baseline.append(identifier)
                remaining -= size
        observed_at = target.created_at
        if observed_at.tzinfo is None:
            from datetime import timezone

            observed_at = observed_at.replace(tzinfo=timezone.utc)
        return FollowUpInput(
            incident_id=target.incident_id,
            baseline=Extraction(
                category=incident.category, summary=incident.observed_condition[:2000]
            ),
            baseline_evidence_ids=baseline,
            follow_up_evidence_ids=current,
            text=target.text,
            same_location_confirmed=target.same_location_confirmed,
            observed_at=observed_at,
        )
