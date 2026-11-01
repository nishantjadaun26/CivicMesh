"""Owner-run schema provisioning. Never invoked by the API or worker startup."""

import argparse
import asyncio

from backend.app.core.config import get_settings
from backend.app.core.tls import checkpoint_tls


def _safe_failure_detail(error: Exception) -> str:
    """Return actionable database diagnostics without exposing connection data."""
    sqlstate = getattr(error, "sqlstate", None) or getattr(error, "pgcode", None)
    if sqlstate:
        categories = {
            "28P01": "database authentication rejected",
            "3D000": "database name not found",
            "42501": "database permission denied",
        }
        return f"SQLSTATE {sqlstate}: {categories.get(sqlstate, 'database operation failed')}"

    # Driver messages can contain hostnames, usernames, or other connection details.
    # Inspect only for safe categories; never print the original message.
    message = str(error).lower()
    if "certificate" in message or "ssl" in message or "tls" in message:
        return "TLS certificate verification failed"
    if "could not translate host" in message or "name or service not known" in message:
        return "database hostname could not be resolved"
    if "timeout" in message or "timed out" in message:
        return "database connection timed out"
    if "password authentication failed" in message:
        return "database authentication rejected"
    return "check the session-pooler host, port, credentials, and TLS settings"


async def apply():
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    from psycopg import AsyncConnection
    from psycopg.rows import dict_row

    settings = get_settings()
    if not settings.CHECKPOINT_DATABASE_URL:
        raise RuntimeError("Set CHECKPOINT_DATABASE_URL before explicit provisioning")
    async with await AsyncConnection.connect(
        settings.CHECKPOINT_DATABASE_URL,
        autocommit=True,
        prepare_threshold=0,
        row_factory=dict_row,
        options="-c search_path=civicmesh_checkpoints,public",
        **checkpoint_tls(settings),
    ) as conn:
        await conn.execute("CREATE SCHEMA IF NOT EXISTS civicmesh_checkpoints")
        await conn.execute(
            "REVOKE ALL ON SCHEMA civicmesh_checkpoints FROM PUBLIC, anon, authenticated, service_role"
        )
        await AsyncPostgresSaver(conn).setup()
        await conn.execute(
            "REVOKE ALL ON ALL TABLES IN SCHEMA civicmesh_checkpoints FROM PUBLIC, anon, authenticated, service_role"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Provision private LangGraph tables after reviewing staging migrations."
    )
    parser.add_argument(
        "--apply", action="store_true", help="Actually modify the configured checkpoint database"
    )
    arguments = parser.parse_args()
    if not arguments.apply:
        print(
            "Plan only: create/upgrade LangGraph tables in civicmesh_checkpoints and revoke public access. No connection made."
        )
    else:
        try:
            asyncio.run(apply())
            print("Checkpoint provisioning completed. Validate staging access before production.")
        except Exception as error:
            print(
                f"Checkpoint provisioning failed ({type(error).__name__}); "
                f"{_safe_failure_detail(error)}. Connection details omitted."
            )
            raise SystemExit(1) from None
