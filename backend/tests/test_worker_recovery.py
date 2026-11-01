"""Crash windows, stale leases and cross-worker exclusion use persisted state."""

from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from backend.app.core.errors import ServiceUnavailableError
from backend.app.database.models import Job, utc_now
from backend.app.worker.locks import JobLocks
from backend.app.worker.runner import Worker
from backend.tests.test_worker_integration import answer, auth, work
from backend.tests.workflow_provider import TestProvider
from civicmesh_ai.checkpoints import sqlite_checkpointer
from psycopg import InterfaceError, OperationalError

pytestmark = pytest.mark.asyncio


async def test_checkpoint_recovers_when_result_commit_fails_without_replaying_approval(
    client, db_session, tmp_path, monkeypatch
):
    owner = uuid4()
    created = (
        await client.post(
            "/reports",
            headers=auth(owner),
            json={
                "text": "Discarded bags cover the pavement.",
                "location": {"latitude": 1, "longitude": 2, "confirmed": True},
            },
        )
    ).json()
    provider = TestProvider()
    async with sqlite_checkpointer(tmp_path / "recovery.sqlite") as saver:
        await work(saver, provider, db_session)
        db_session.expire_all()
        await answer(client, owner, created["job_id"], {"approved": True})
        original_process = Worker.process

        async def fail_after_graph(self, db, job, target):
            original_commit = db.commit

            async def fail_once():
                db.commit = original_commit
                raise ServiceUnavailableError("Isolated simulated persistence outage")

            db.commit = fail_once
            try:
                await original_process(self, db, job, target)
            finally:
                db.commit = original_commit

        monkeypatch.setattr(Worker, "process", fail_after_graph)
        await work(saver, provider, db_session)
        monkeypatch.setattr(Worker, "process", original_process)
        db_session.expire_all()
        job = await db_session.get(Job, UUID(created["job_id"]))
        assert job.status == "pending" and job.failures == 1
        job.available_at = utc_now() - timedelta(seconds=1)
        await db_session.commit()
        await work(saver, provider, db_session)
        db_session.expire_all()
        view = (await client.get(f"/jobs/{created['job_id']}", headers=auth(owner))).json()
        assert view["status"] == "completed"
        assert view["result"]["workflow_status"] == "authority_unavailable"
        assert provider.calls == 1


async def test_held_workflow_excludes_another_worker(client, db_session, tmp_path):
    created = (
        await client.post("/reports", headers=auth(uuid4()), json={"text": "Isolated observation"})
    ).json()
    async with sqlite_checkpointer(tmp_path / "locks.sqlite") as saver:
        async with JobLocks(db_session.bind).try_hold(UUID(created["job_id"])) as acquired:
            assert acquired
            assert not await work(saver, TestProvider(), db_session)
        assert await work(saver, TestProvider(), db_session)


async def test_crash_lease_consumes_failure_budget_and_never_restarts_unboundedly(
    client, db_session, tmp_path
):
    created = (
        await client.post("/reports", headers=auth(uuid4()), json={"text": "Isolated observation"})
    ).json()
    job = await db_session.get(Job, UUID(created["job_id"]))
    job.status, job.locked_at, job.locked_by = "running", utc_now(), "dead-isolated-worker"
    job.failures = 2
    await db_session.commit()
    provider = TestProvider()
    async with sqlite_checkpointer(tmp_path / "lease.sqlite") as saver:
        assert not await work(saver, provider, db_session)
        job.locked_at = utc_now() - timedelta(seconds=601)
        await db_session.commit()
        assert await work(saver, provider, db_session)
    db_session.expire_all()
    job = await db_session.get(Job, UUID(created["job_id"]))
    assert job.status == "failed" and job.failures == 3
    assert provider.calls == 0


async def test_lost_checkpoint_does_not_silently_restart_a_reviewed_report(
    client, db_session, tmp_path
):
    owner = uuid4()
    created = (
        await client.post(
            "/reports",
            headers=auth(owner),
            json={
                "text": "Discarded bags cover the pavement.",
                "location": {"latitude": 1, "longitude": 2, "confirmed": True},
            },
        )
    ).json()
    provider = TestProvider()
    async with sqlite_checkpointer(tmp_path / "original.sqlite") as saver:
        await work(saver, provider, db_session)
    db_session.expire_all()
    await answer(client, owner, created["job_id"], {"approved": True})
    async with sqlite_checkpointer(tmp_path / "missing.sqlite") as saver:
        await work(saver, provider, db_session)
    db_session.expire_all()
    job = (await client.get(f"/jobs/{created['job_id']}", headers=auth(owner))).json()
    assert job["status"] == "failed" and job["error_code"] == "checkpoint_unavailable"
    assert provider.calls == 1


@pytest.mark.parametrize("failure", [OperationalError, InterfaceError])
async def test_checkpoint_connection_errors_retry_without_starting_paid_work(
    client, db_session, tmp_path, monkeypatch, failure
):
    owner = uuid4()
    created = (
        await client.post("/reports", headers=auth(owner), json={"text": "Isolated observation"})
    ).json()
    provider = TestProvider()
    async with sqlite_checkpointer(tmp_path / "connection-recovery.sqlite") as saver:
        original = saver.aget_tuple
        first = True

        async def interrupted(config):
            nonlocal first
            if first:
                first = False
                raise failure("isolated-sensitive-connection-detail")
            return await original(config)

        monkeypatch.setattr(saver, "aget_tuple", interrupted)
        assert await work(saver, provider, db_session)
        db_session.expire_all()
        job = await db_session.get(Job, UUID(created["job_id"]))
        assert job.status == "pending" and job.failures == 1 and provider.calls == 0
        view = await client.get(f"/jobs/{job.id}", headers=auth(owner))
        assert "isolated-sensitive-connection-detail" not in view.text
        job.available_at = utc_now() - timedelta(seconds=1)
        await db_session.commit()
        assert await work(saver, provider, db_session)
        db_session.expire_all()
        job = await db_session.get(Job, UUID(created["job_id"]))
        assert job.status == "waiting_for_input" and provider.calls == 1


async def test_unavailable_checkpoint_store_cannot_refresh_worker_readiness(db_session):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from backend.app.database.models import WorkerHeartbeat
    from backend.tests.conftest import get_test_settings
    from sqlalchemy import func, select
    from sqlalchemy.ext.asyncio import async_sessionmaker

    worker = Worker(
        sessions=async_sessionmaker(db_session.bind, expire_on_commit=False),
        engine=db_session.bind,
        provider=TestProvider(),
        settings=get_test_settings(),
        saver=SimpleNamespace(
            aget_tuple=AsyncMock(side_effect=OperationalError("isolated outage"))
        ),
    )
    with pytest.raises(OperationalError):
        await worker.heartbeat()
    assert (
        await db_session.execute(select(func.count()).select_from(WorkerHeartbeat))
    ).scalar_one() == 0
