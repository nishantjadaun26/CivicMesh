"""Session-level PostgreSQL exclusion through checkpoint and job persistence."""

import asyncio
from contextlib import asynccontextmanager
from weakref import WeakValueDictionary

from sqlalchemy import text

_local_locks = WeakValueDictionary()


class JobLocks:
    def __init__(self, engine):
        self.engine = engine

    @asynccontextmanager
    async def try_hold(self, job_id):
        if self.engine.dialect.name == "postgresql":
            key = int.from_bytes(job_id.bytes[:8], byteorder="big", signed=True)
            async with self.engine.connect() as connection:
                acquired = (
                    await connection.execute(
                        text("SELECT pg_try_advisory_lock(:key)"), {"key": key}
                    )
                ).scalar_one()
                await connection.commit()
                try:
                    yield acquired
                finally:
                    if acquired:
                        await connection.execute(
                            text("SELECT pg_advisory_unlock(:key)"), {"key": key}
                        )
                        await connection.commit()
        else:
            # SQLite is explicitly development/test-only, in one worker process.
            key = str(job_id)
            lock = _local_locks.get(key)
            if lock is None:
                lock = asyncio.Lock()
                _local_locks[key] = lock
            if lock.locked():
                yield False
            else:
                async with lock:
                    yield True


class HeldWorkflowLock:
    """The outer job lock remains held through coordinator calls AND result commit."""

    def __init__(self, workflow_id):
        self.workflow_id = workflow_id

    @asynccontextmanager
    async def hold(self, workflow_id):
        if workflow_id != self.workflow_id:
            raise RuntimeError("Workflow lock context mismatch")
        yield
