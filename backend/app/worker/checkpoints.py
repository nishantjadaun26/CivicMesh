"""Private checkpoint schema. Schema provisioning is an explicit owner operation."""

from contextlib import asynccontextmanager
from pathlib import Path

from backend.app.core.tls import checkpoint_tls
from civicmesh_ai.checkpoints import sqlite_checkpointer


@asynccontextmanager
async def open_checkpointer(settings):
    if settings.CHECKPOINT_DATABASE_URL:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        from psycopg.rows import dict_row
        from psycopg_pool import AsyncConnectionPool

        async with AsyncConnectionPool(
            settings.CHECKPOINT_DATABASE_URL,
            min_size=1,
            max_size=1,
            open=False,
            timeout=5,
            reconnect_timeout=10,
            check=AsyncConnectionPool.check_connection,
            kwargs={
                "autocommit": True,
                "prepare_threshold": 0,
                "row_factory": dict_row,
                "connect_timeout": 5,
                "options": "-c search_path=civicmesh_checkpoints,public",
                **checkpoint_tls(settings),
            },
        ) as pool:
            await pool.wait(timeout=10)
            async with pool.connection() as connection:
                if settings.ENVIRONMENT == "production" and not connection.pgconn.ssl_in_use:
                    raise RuntimeError("Checkpoint connection requires TLS")
                await connection.execute("SELECT 1 FROM civicmesh_checkpoints.checkpoints LIMIT 0")
            # Each saver operation borrows a checked connection. Broken connections
            # are discarded and replaced without leaving a permanently poisoned saver.
            yield AsyncPostgresSaver(pool)
    else:
        if settings.ENVIRONMENT == "production":
            raise RuntimeError("Production requires CHECKPOINT_DATABASE_URL")
        path = Path(settings.LOCAL_CHECKPOINT_PATH)
        path.parent.mkdir(parents=True, exist_ok=True)
        async with sqlite_checkpointer(path) as saver:
            yield saver
