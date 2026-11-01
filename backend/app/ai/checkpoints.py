"""Replaceable durable checkpointers; never create remote schemas on import/startup."""

from contextlib import asynccontextmanager
from pathlib import Path

from civicmesh_ai.errors import AIError


@asynccontextmanager
async def sqlite_checkpointer(path: Path):
    """Open a local development checkpoint file; it contains private report state."""
    if str(path) == ":memory:":
        raise AIError("durable_path_required", "Provide a file path for durable local checkpoints.")
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

    async with AsyncSqliteSaver.from_conn_string(str(path)) as saver:
        yield saver


@asynccontextmanager
async def postgres_checkpointer(connection_string: str):
    """Open backend-provisioned PostgreSQL checkpoints without running schema setup.

    Backend must inspect its database, explicitly run saver.setup() in its migration
    process, and supply a secret psycopg DSN with TLS before using this adapter.
    """
    if not connection_string.startswith(("postgresql://", "postgres://")):
        raise AIError("invalid_checkpoint_config", "Use a PostgreSQL DSN, not a SQLAlchemy URL.")
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    async with AsyncPostgresSaver.from_conn_string(connection_string) as saver:
        yield saver
    # The backend must sanitize DB exceptions; do not log the connection string.
