"""Owner-scoped start/read/resume facade over the AI graphs, without an HTTP API."""

import asyncio
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Protocol
from uuid import UUID
from weakref import WeakValueDictionary

from civicmesh_ai.assessment import FollowUpInput
from civicmesh_ai.errors import AIError
from civicmesh_ai.graph.follow_up import build_follow_up_workflow, initial_follow_up_state
from civicmesh_ai.graph.report import build_report_workflow, initial_report_state
from civicmesh_ai.identity import owner
from civicmesh_ai.integration import (
    FollowUpCompletion,
    PendingAction,
    ReportCompletion,
    WorkflowKind,
    WorkflowView,
)
from civicmesh_ai.schemas import Clarification, ReportInput, ReviewDecision
from langgraph.types import Command
from pydantic import ValidationError


class WorkflowLocks(Protocol):
    """Backend supplies mutual exclusion across its workers for each persisted workflow."""

    def hold(self, workflow_id: UUID) -> AbstractAsyncContextManager[None]:
        """Hold an exclusive workflow lock through checkpoint reads and graph invocation."""
        ...


class InProcessWorkflowLocks:
    """Single-event-loop development/test locks; not a distributed production lock."""

    def __init__(self):
        """Weak references release lock entries after all holders/waiters finish."""
        self._locks = WeakValueDictionary()

    @asynccontextmanager
    async def hold(self, workflow_id: UUID):
        """Serialize a workflow inside one coordinator process/event loop."""
        key = str(workflow_id)
        lock = self._locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[key] = lock
        async with lock:
            yield


class WorkflowCoordinator:
    """Caller identity must already be authenticated and authorized by the backend.

    No method accepts raw graph state or client-selected owner changes. Production
    callers must share a distributed lock implementation and durable checkpointer.
    """

    def __init__(self, provider, *, tools, checkpointer, locks: WorkflowLocks):
        """Require explicit storage, tools and locking; no implicit production fallbacks."""
        if locks is None:
            raise AIError("workflow_not_configured", "A workflow lock adapter is required.")
        self.saver = checkpointer
        self.locks = locks
        self.graphs = {
            "report": build_report_workflow(provider, tools=tools, checkpointer=checkpointer),
            "follow_up": build_follow_up_workflow(provider, tools=tools, checkpointer=checkpointer),
        }

    @staticmethod
    def _config(workflow_id: UUID, kind: WorkflowKind | None = None):
        """Use a namespaced persisted ID and preserve graph-kind metadata on every write."""
        config = {"configurable": {"thread_id": f"civicmesh:{workflow_id}"}}
        if kind is not None:
            config["metadata"] = {"civicmesh_workflow_kind": kind}
        return config

    async def _read(self, workflow_id: UUID, owner_id: UUID):
        """Resolve the saved graph kind, then reject cross-owner access before returning data."""
        checkpoint = await self.saver.aget_tuple(self._config(workflow_id))
        if checkpoint is None:
            raise AIError("workflow_not_found", "Workflow is unavailable.")
        kind = checkpoint.metadata.get("civicmesh_workflow_kind")
        if kind not in self.graphs:
            raise AIError("invalid_workflow_state", "Saved workflow kind is unsupported.")
        graph = self.graphs[kind]
        snapshot = await graph.aget_state(self._config(workflow_id, kind))
        if owner(snapshot.values) != owner_id:
            raise AIError("workflow_not_found", "Workflow is unavailable.")
        return kind, graph, snapshot

    @staticmethod
    def _view(workflow_id: UUID, kind: WorkflowKind, snapshot) -> WorkflowView:
        """Expose validated outcomes and pending prompts rather than raw state or task errors."""
        pending = []
        for action in snapshot.interrupts:
            payload = action.value
            if not isinstance(payload, dict):
                raise AIError("invalid_workflow_state", "Saved workflow action is invalid.")
            pending.append(
                PendingAction(interrupt_id=action.id, kind=payload.get("kind"), payload=payload)
            )
        status = "waiting_for_input" if pending else "incomplete" if snapshot.next else "completed"
        output = None
        if status == "completed":
            values = snapshot.values
            if kind == "report":
                result = values["result"]
                output = ReportCompletion(
                    extraction_result=result,
                    workflow_status=values.get("workflow_status", result["status"]),
                    candidates=values.get("candidates", []),
                    priority=values.get("priority"),
                    recommendation=values.get("recommendation"),
                    packet=values.get("packet"),
                )
            else:
                output = FollowUpCompletion.model_validate(values["result"])
        return WorkflowView(
            workflow_id=workflow_id,
            kind=kind,
            checkpoint_id=snapshot.config["configurable"]["checkpoint_id"],
            status=status,
            pending=pending,
            has_failed_step=any(task.error for task in snapshot.tasks),
            output=output,
        )

    async def _start(self, workflow_id: UUID, owner_id: UUID, kind: WorkflowKind, state):
        """Reject reused IDs instead of overwriting an existing workflow or re-paying for it."""
        async with self.locks.hold(workflow_id):
            if await self.saver.aget_tuple(self._config(workflow_id)) is not None:
                await self._read(workflow_id, owner_id)
                raise AIError(
                    "workflow_exists", "Workflow already exists; inspect its current state."
                )
            await self.graphs[kind].ainvoke(state, self._config(workflow_id, kind))
            saved_kind, _, snapshot = await self._read(workflow_id, owner_id)
            return self._view(workflow_id, saved_kind, snapshot)

    async def start_report(
        self, workflow_id: UUID, *, owner_id: UUID, report: ReportInput
    ) -> WorkflowView:
        """Start report processing using persisted IDs and authenticated backend context."""
        workflow_id, owner_id = UUID(str(workflow_id)), UUID(str(owner_id))
        return await self._start(
            workflow_id, owner_id, "report", initial_report_state(report, owner_id=owner_id)
        )

    async def start_follow_up(
        self, workflow_id: UUID, *, owner_id: UUID, request: FollowUpInput
    ) -> WorkflowView:
        """Start follow-up assessment using references already authorized by the backend."""
        workflow_id, owner_id = UUID(str(workflow_id)), UUID(str(owner_id))
        return await self._start(
            workflow_id, owner_id, "follow_up", initial_follow_up_state(request, owner_id=owner_id)
        )

    async def inspect(self, workflow_id: UUID, *, owner_id: UUID) -> WorkflowView:
        """Return the owner's latest typed status and pending review, without changing it."""
        workflow_id, owner_id = UUID(str(workflow_id)), UUID(str(owner_id))
        async with self.locks.hold(workflow_id):
            kind, _, snapshot = await self._read(workflow_id, owner_id)
            return self._view(workflow_id, kind, snapshot)

    async def resume(
        self,
        workflow_id: UUID,
        *,
        owner_id: UUID,
        checkpoint_id: str,
        interrupt_id: str,
        reply: dict,
    ) -> WorkflowView:
        """Validate stage, owner and checkpoint under lock before resuming one exact action."""
        workflow_id, owner_id = UUID(str(workflow_id)), UUID(str(owner_id))
        async with self.locks.hold(workflow_id):
            kind, graph, snapshot = await self._read(workflow_id, owner_id)
            current = self._view(workflow_id, kind, snapshot)
            if current.checkpoint_id != checkpoint_id:
                raise AIError("stale_workflow", "Workflow changed; reload its current review.")
            if current.status != "waiting_for_input" or len(current.pending) != 1:
                raise AIError("workflow_not_waiting", "Workflow has no pending input.")
            action = current.pending[0]
            if action.interrupt_id != interrupt_id:
                raise AIError("stale_workflow", "Review action changed; reload the workflow.")
            schema = Clarification if action.kind == "clarification" else ReviewDecision
            try:
                validated = schema.model_validate(reply).model_dump(mode="json")
            except ValidationError:
                raise AIError(
                    "invalid_workflow_reply", "Reply does not match the pending action."
                ) from None
            await graph.ainvoke(
                Command(resume={interrupt_id: validated}), self._config(workflow_id, kind)
            )
            _, _, updated = await self._read(workflow_id, owner_id)
            return self._view(workflow_id, kind, updated)

    async def retry(self, workflow_id: UUID, *, owner_id: UUID, checkpoint_id: str) -> WorkflowView:
        """Continue an interrupted execution step once; persistent retry budgets remain worker-owned."""
        workflow_id, owner_id = UUID(str(workflow_id)), UUID(str(owner_id))
        async with self.locks.hold(workflow_id):
            kind, graph, snapshot = await self._read(workflow_id, owner_id)
            current = self._view(workflow_id, kind, snapshot)
            if current.checkpoint_id != checkpoint_id:
                raise AIError("stale_workflow", "Workflow changed; reload its current state.")
            if current.status != "incomplete":
                raise AIError(
                    "workflow_not_retryable", "Only an incomplete execution step can be retried."
                )
            await graph.ainvoke(None, self._config(workflow_id, kind))
            _, _, updated = await self._read(workflow_id, owner_id)
            return self._view(workflow_id, kind, updated)
