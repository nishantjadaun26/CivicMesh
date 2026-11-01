"""Offline verification of the backend-facing lifecycle and owner/review boundaries."""

import asyncio
from uuid import UUID

import pytest
from civicmesh_ai.checkpoints import sqlite_checkpointer
from civicmesh_ai.coordinator import InProcessWorkflowLocks, WorkflowCoordinator
from civicmesh_ai.errors import AIError
from langgraph.checkpoint.memory import InMemorySaver
from test_follow_up import EvidenceTools, FollowUpProvider, request_for_test
from test_report_pipeline import BackendDouble, ProviderDouble


def coordinator(provider=None, *, saver=None, locks=None):
    """Create an isolated coordinator with explicit single-process fixture dependencies."""
    return WorkflowCoordinator(
        provider if provider is not None else ProviderDouble(),
        tools=BackendDouble(),
        checkpointer=saver if saver is not None else InMemorySaver(),
        locks=locks if locks is not None else InProcessWorkflowLocks(),
    )


async def approve(service, view, *, owner_id=UUID(int=9)):
    """Approve the exact checkpoint/action returned by a prior owner-authorized read."""
    return await service.resume(
        view.workflow_id,
        owner_id=owner_id,
        checkpoint_id=view.checkpoint_id,
        interrupt_id=view.pending[0].interrupt_id,
        reply={"approved": True},
    )


def test_typed_report_start_inspect_and_final_packet(report):
    """Expose prompts and a validated unsubmitted packet without returning raw checkpoint state."""

    async def scenario():
        service = coordinator()
        first = await service.start_report(UUID(int=20), owner_id=UUID(int=9), report=report)
        assert first.status == "waiting_for_input"
        assert first.pending[0].kind == "extraction_review"
        assert first.output is None
        assert await service.inspect(first.workflow_id, owner_id=UUID(int=9)) == first
        second = await approve(service, first)
        assert second.pending[0].kind == "complaint_review"
        final = await approve(service, second)
        assert final.status == "completed"
        assert final.output.workflow_status == "approved_draft"
        assert final.output.packet.submitted is False
        assert final.output.packet.authority_status == "unknown"
        assert "report" not in final.model_dump()
        assert "owner_id" not in final.model_dump()

    asyncio.run(scenario())


def test_reused_workflow_ids_never_restart_or_overwrite(report):
    """Starting an existing ID rejects before any duplicate paid extraction."""

    async def scenario():
        provider = ProviderDouble()
        service = coordinator(provider)
        first = await service.start_report(UUID(int=20), owner_id=UUID(int=9), report=report)
        with pytest.raises(AIError) as error:
            await service.start_report(first.workflow_id, owner_id=UUID(int=9), report=report)
        assert error.value.code == "workflow_exists"
        assert [call[0] for call in provider.calls] == ["extract"]
        assert await service.inspect(first.workflow_id, owner_id=UUID(int=9)) == first

    asyncio.run(scenario())


def test_cross_owner_inspect_resume_retry_and_start_are_rejected(report):
    """Caller-supplied workflow IDs never grant access to another owner's private state."""

    async def scenario():
        provider = ProviderDouble()
        service = coordinator(provider)
        first = await service.start_report(UUID(int=20), owner_id=UUID(int=9), report=report)
        operations = [
            lambda: service.inspect(first.workflow_id, owner_id=UUID(int=8)),
            lambda: approve(service, first, owner_id=UUID(int=8)),
            lambda: service.retry(
                first.workflow_id, owner_id=UUID(int=8), checkpoint_id=first.checkpoint_id
            ),
            lambda: service.start_report(first.workflow_id, owner_id=UUID(int=8), report=report),
        ]
        for operation in operations:
            with pytest.raises(AIError) as error:
                await operation()
            assert error.value.code == "workflow_not_found"
        assert len(provider.calls) == 1

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "bad_reply",
    [{"approved": "true"}, {"approved": True, "owner_id": "injected"}, {"text": "wrong stage"}],
)
def test_invalid_replies_do_not_mutate_checkpoints_or_call_models(report, bad_reply):
    """Validate the action-specific payload before passing a resume command to LangGraph."""

    async def scenario():
        provider = ProviderDouble()
        service = coordinator(provider)
        first = await service.start_report(UUID(int=20), owner_id=UUID(int=9), report=report)
        with pytest.raises(AIError) as error:
            await service.resume(
                first.workflow_id,
                owner_id=UUID(int=9),
                checkpoint_id=first.checkpoint_id,
                interrupt_id=first.pending[0].interrupt_id,
                reply=bad_reply,
            )
        assert error.value.code == "invalid_workflow_reply"
        assert await service.inspect(first.workflow_id, owner_id=UUID(int=9)) == first
        assert len(provider.calls) == 1

    asyncio.run(scenario())


def test_stale_and_concurrent_review_replies_cannot_approve_the_next_stage(report):
    """Two workers sharing a lock accept one reply; the duplicate cannot approve a draft."""

    async def scenario():
        provider, saver, locks = ProviderDouble(), InMemorySaver(), InProcessWorkflowLocks()
        first_worker = coordinator(provider, saver=saver, locks=locks)
        second_worker = coordinator(provider, saver=saver, locks=locks)
        first = await first_worker.start_report(UUID(int=20), owner_id=UUID(int=9), report=report)
        with pytest.raises(AIError) as error:
            await first_worker.resume(
                first.workflow_id,
                owner_id=UUID(int=9),
                checkpoint_id=first.checkpoint_id,
                interrupt_id="wrong-action",
                reply={"approved": True},
            )
        assert error.value.code == "stale_workflow"
        replies = await asyncio.gather(
            approve(first_worker, first), approve(second_worker, first), return_exceptions=True
        )
        accepted = [reply for reply in replies if not isinstance(reply, Exception)]
        rejected = [reply for reply in replies if isinstance(reply, AIError)]
        assert len(accepted) == len(rejected) == 1
        assert rejected[0].code == "stale_workflow"
        assert accepted[0].pending[0].kind == "complaint_review"
        assert accepted[0].output is None
        assert [call[0] for call in provider.calls].count("complaint") == 1

    asyncio.run(scenario())


def test_coordinator_clarification_uses_the_current_action_schema(report):
    """Clarification accepts corrected location data, then changes to a review-only reply."""

    async def scenario():
        service = coordinator()
        incomplete = report.model_copy(update={"location": None})
        first = await service.start_report(UUID(int=20), owner_id=UUID(int=9), report=incomplete)
        assert first.pending[0].kind == "clarification"
        second = await service.resume(
            first.workflow_id,
            owner_id=UUID(int=9),
            checkpoint_id=first.checkpoint_id,
            interrupt_id=first.pending[0].interrupt_id,
            reply={"location": report.location.model_dump(mode="json")},
        )
        assert second.pending[0].kind == "extraction_review"

    asyncio.run(scenario())


def test_completed_workflows_cannot_be_resumed_or_retried(report):
    """A terminal rejection stays terminal rather than restarting paid work."""

    async def scenario():
        provider = ProviderDouble()
        service = coordinator(provider)
        first = await service.start_report(UUID(int=20), owner_id=UUID(int=9), report=report)
        done = await service.resume(
            first.workflow_id,
            owner_id=UUID(int=9),
            checkpoint_id=first.checkpoint_id,
            interrupt_id=first.pending[0].interrupt_id,
            reply={"approved": False},
        )
        assert done.output.workflow_status == "rejected"
        with pytest.raises(AIError) as error:
            await service.retry(
                done.workflow_id, owner_id=UUID(int=9), checkpoint_id=done.checkpoint_id
            )
        assert error.value.code == "workflow_not_retryable"
        with pytest.raises(AIError) as error:
            await service.resume(
                done.workflow_id,
                owner_id=UUID(int=9),
                checkpoint_id=done.checkpoint_id,
                interrupt_id=first.pending[0].interrupt_id,
                reply={"approved": True},
            )
        assert error.value.code == "workflow_not_waiting"
        assert len(provider.calls) == 1

    asyncio.run(scenario())


def test_follow_up_completion_has_typed_observation_attribution():
    """Expose a reviewed follow-up result without any official-status mutation."""

    async def scenario():
        service = WorkflowCoordinator(
            FollowUpProvider(),
            tools=EvidenceTools(),
            checkpointer=InMemorySaver(),
            locks=InProcessWorkflowLocks(),
        )
        first = await service.start_follow_up(
            UUID(int=20), owner_id=UUID(int=9), request=request_for_test()
        )
        assert first.kind == "follow_up"
        done = await approve(service, first)
        assert done.output.attribution == "ai_assessment"
        assert done.output.updates_authority_status is False

    asyncio.run(scenario())


def test_incomplete_execution_can_be_retried_once_by_the_worker(report):
    """Resume the failed node, preserving identity and leaving persistent retry budgets external."""

    class FlakyProvider(ProviderDouble):
        """Fail the first isolated provider call before returning its normal test response."""

        def __init__(self):
            """Track retry attempts independently of successful fixture requests."""
            super().__init__()
            self.attempts = 0

        async def extract(self, request, *, media=()):
            """Emit one sanitized transient failure, then allow worker-directed recovery."""
            self.attempts += 1
            if self.attempts == 1:
                raise AIError("provider_unavailable", "Test-only transient error.", retryable=True)
            return await super().extract(request, media=media)

    async def scenario():
        provider = FlakyProvider()
        service = coordinator(provider)
        with pytest.raises(AIError):
            await service.start_report(UUID(int=20), owner_id=UUID(int=9), report=report)
        failed = await service.inspect(UUID(int=20), owner_id=UUID(int=9))
        assert failed.status == "incomplete"
        assert failed.has_failed_step
        assert "Test-only transient error" not in failed.model_dump_json()
        current = await service.retry(
            failed.workflow_id, owner_id=UUID(int=9), checkpoint_id=failed.checkpoint_id
        )
        assert current.pending[0].kind == "extraction_review"
        assert provider.attempts == 2

    asyncio.run(scenario())


def test_coordinator_kind_and_action_survive_checkpoint_reopen(tmp_path, report):
    """A newly constructed coordinator can recover graph kind and private pending review."""
    pytest.importorskip("langgraph.checkpoint.sqlite")
    database = tmp_path / "coordinator.sqlite"

    async def scenario():
        async with sqlite_checkpointer(database) as saver:
            service = coordinator(saver=saver)
            first = await service.start_report(UUID(int=20), owner_id=UUID(int=9), report=report)
        async with sqlite_checkpointer(database) as saver:
            service = coordinator(saver=saver)
            assert await service.inspect(first.workflow_id, owner_id=UUID(int=9)) == first
            second = await approve(service, first)
            assert second.pending[0].kind == "complaint_review"

    asyncio.run(scenario())
