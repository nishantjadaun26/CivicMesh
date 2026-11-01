"""Private checkpoint schema. Schema provisioning is an explicit owner operation."""

from contextlib import asynccontextmanager
from pathlib import Path

from backend.app.core.tls import checkpoint_tls
from civicmesh_ai.checkpoints import sqlite_checkpointer


@asynccontextmanager
async def open_checkpointer(settings):
    if settings.CHECKPOINT_DATABASE_URL:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        from psycopg import AsyncConnection
        from psycopg.rows import dict_row

        async with await AsyncConnection.connect(
            settings.CHECKPOINT_DATABASE_URL,
            autocommit=True,
            prepare_threshold=0,
            row_factory=dict_row,
            options="-c search_path=civicmesh_checkpoints,public",
            **checkpoint_tls(settings),
        ) as connection:
            if settings.ENVIRONMENT == "production" and not connection.pgconn.ssl_in_use:
                raise RuntimeError("Checkpoint connection requires TLS")
            async with connection.cursor() as cursor:
                await cursor.execute("SELECT 1 FROM civicmesh_checkpoints.checkpoints LIMIT 0")
            yield AsyncPostgresSaver(connection)
    else:
        if settings.ENVIRONMENT == "production":
            raise RuntimeError("Production requires CHECKPOINT_DATABASE_URL")
        path = Path(settings.LOCAL_CHECKPOINT_PATH)
        path.parent.mkdir(parents=True, exist_ok=True)
        async with sqlite_checkpointer(path) as saver:
            yield saver
