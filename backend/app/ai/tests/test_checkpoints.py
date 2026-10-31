"""Durable restart/resume on local SQLite; PostgreSQL is not claimed tested."""

import asyncio
import json
import subprocess
import sys
from pathlib import Path
from uuid import UUID

import pytest
from civicmesh_ai.checkpoints import postgres_checkpointer, sqlite_checkpointer
from civicmesh_ai.errors import AIError
from civicmesh_ai.graph.report import build_report_workflow, initial_report_state
from langgraph.types import Command
from test_report_pipeline import BackendDouble, ProviderDouble


def test_full_workflow_resumes_in_a_new_process(tmp_path, report):
    """Persist both review boundaries and resume in another process without re-extraction."""
    pytest.importorskip("langgraph.checkpoint.sqlite")
    database = tmp_path / "checkpoints.sqlite"
    config = {"configurable": {"thread_id": "durable-test"}}

    async def begin():
        """Close the initial saver after the extraction review is durably checkpointed."""
        async with sqlite_checkpointer(database) as saver:
            graph = build_report_workflow(
                ProviderDouble(), tools=BackendDouble(), checkpointer=saver
            )
            result = await graph.ainvoke(initial_report_state(report, owner_id=UUID(int=9)), config)
            assert result["__interrupt__"][0].value["kind"] == "extraction_review"

    asyncio.run(begin())
    child = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).with_name("checkpoint_restart_helper.py")),
            str(database),
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    child_result = json.loads(child.stdout)
    assert child_result == {
        "kind": "complaint_review",
        "calls": ["priority", "authority", "complaint"],
    }

    async def finish():
        """Reopen the saved complaint review and approve without re-running model steps."""
        provider = ProviderDouble()
        async with sqlite_checkpointer(database) as saver:
            graph = build_report_workflow(provider, tools=BackendDouble(), checkpointer=saver)
            result = await graph.ainvoke(Command(resume={"approved": True}), config)
            assert result["workflow_status"] == "approved_draft"
            assert not provider.calls

    asyncio.run(finish())


def test_invalid_checkpoint_configuration_is_rejected_before_connecting():
    """Refuse in-memory paths and SQLAlchemy DSNs where durable raw-driver config is required."""

    async def scenario():
        """Exercise invalid checkpoint configuration is rejected before connecting in one event loop."""
        with pytest.raises(AIError):
            async with sqlite_checkpointer(Path(":memory:")):
                pass
        with pytest.raises(AIError):
            async with postgres_checkpointer("postgresql+psycopg://not-a-real-database"):
                pass

    asyncio.run(scenario())
