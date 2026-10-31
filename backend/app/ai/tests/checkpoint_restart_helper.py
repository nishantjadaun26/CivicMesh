"""Fresh-process resume helper; isolated test doubles only, no model/network calls."""

import asyncio
import json
import sys
from pathlib import Path

from civicmesh_ai.checkpoints import sqlite_checkpointer
from civicmesh_ai.graph.report import build_report_workflow
from langgraph.types import Command
from test_report_pipeline import BackendDouble, ProviderDouble


async def main():
    """Resume a saved review in a distinct process and report which provider steps ran."""
    provider = ProviderDouble()
    async with sqlite_checkpointer(Path(sys.argv[1])) as saver:
        graph = build_report_workflow(provider, tools=BackendDouble(), checkpointer=saver)
        result = await graph.ainvoke(
            Command(resume={"approved": True}), {"configurable": {"thread_id": "durable-test"}}
        )
        print(
            json.dumps(
                {
                    "kind": result["__interrupt__"][0].value["kind"],
                    "calls": [call[0] for call in provider.calls],
                }
            )
        )


if __name__ == "__main__":
    asyncio.run(main())
