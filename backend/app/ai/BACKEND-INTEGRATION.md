# AI integration for the backend teammate

Install `backend/app/ai` as the local `civicmesh_ai` package, including the `checkpoints`
extra when using its durable adapters. `WorkflowCoordinator` is the recommended worker
entry point. It is a library, not an HTTP server, JWT verifier, job queue or storage service.

## Supply these dependencies

- GeminiProvider configured with worker-only GEMINI_API_KEY and GEMINI_MODEL.
- Your implementation of BackendTools for authorized media, matching and official sources.
- An initialized durable checkpoint saver; use the installed PostgreSQL adapter after
  reviewing and provisioning its schema. No schema changes are made by the coordinator.
- A WorkflowLocks implementation that excludes simultaneous operations on the same workflow
  across **all** your worker processes. Its hold(workflow_id) must remain held through the
  checkpoint read and graph invocation. InProcessWorkflowLocks is only for single-event-loop
  local development/tests; it does not supply distributed exclusion or process-crash fencing.

Use identities, workflow IDs, report IDs and incident IDs from your authenticated application
and persistent records. Never take owner_id directly from an unverified request or model output.

## Start an existing queued report

The following is an integration outline with backend-supplied arguments, not fixture data:

```python
from civicmesh_ai.coordinator import WorkflowCoordinator
from civicmesh_ai.schemas import ReportInput

async def run_queued_report(provider, tools, saver, locks,
                            workflow_id, verified_owner_id, stored_report_payload):
    coordinator = WorkflowCoordinator(
        provider, tools=tools, checkpointer=saver, locks=locks
    )
    return await coordinator.start_report(
        workflow_id,
        owner_id=verified_owner_id,
        report=ReportInput.model_validate(stored_report_payload),
    )
```

For follow-ups, validate FollowUpInput and call start_follow_up(workflow_id,
owner_id=verified_owner_id, request=validated_follow_up). All coordinator operations use
the checkpoint thread name `civicmesh:<workflow_id>` and retain workflow-kind metadata.
Do not use these threads through direct graph commands or arbitrary client state updates.

## Read, display and resume a review

1. Verify the logged-in user's access to the report/incident/job in your application.
2. Call coordinator.inspect(workflow_id, owner_id=verified_owner_id).
3. If status is waiting_for_input, return only the owner's pending prompt through your API.
   Its payload includes citizen data and can contain private evidence/source references;
   never publish it as a public incident or render its text as trusted HTML/instructions.
4. Retain checkpoint_id and the pending action's interrupt_id with the displayed prompt.
5. Submit the user's reply with **those same IDs**, then call:

```python
view = await coordinator.resume(
    workflow_id,
    owner_id=verified_owner_id,
    checkpoint_id=displayed_checkpoint_id,
    interrupt_id=displayed_interrupt_id,
    reply=answer_payload,
)
```

Clarification accepts text/category/confirmed location. Review accepts a strict boolean
approved field. The coordinator validates the action-specific reply before changing the
checkpoint. Owner, checkpoint and interrupt checks are performed under your supplied lock.
It refuses stale replies rather than applying them to a later review. Duplicate starts are
refused instead of overwriting a report or silently repeating paid extraction.

## Persist results and job state

WorkflowView is a Pydantic model. Its JSON schema can be included in your FastAPI models
and your shared OpenAPI contract rather than independently copying these definitions.
The view intentionally omits raw checkpoint state, original answer history and task errors.

| View state | Backend action |
| --- | --- |
| waiting_for_input | Persist job waiting state and expose the private pending action to its authorized user/reviewer |
| completed, report | Persist typed ReportCompletion, candidates, priority, supported routing and optional complaint packet |
| completed, follow_up | Persist typed FollowUpCompletion as an attributed observation; preserve authority status |
| incomplete | Inspect your worker's failure record and retry policy; do not report success or an empty operational result |

Rejected drafts and needs_information are completed AI outcomes, not successful submissions.
An approved complaint packet still has submitted=false and authority_status=unknown.
An actual external submission, if added, requires a separate authorized and idempotent backend
operation; this package does not send anything or create an authority receipt.

## Failure and retry handling

An interrupted model/backend operation raises to the worker. Store a sanitized error and
bounded attempt count on the persistent job. A saved WorkflowView may be incomplete with
has_failed_step=true, but its response never contains the raw error string.

After a retryable failure and within your durable retry budget, call:

```python
current = await coordinator.inspect(workflow_id, owner_id=verified_owner_id)
view = await coordinator.retry(
    workflow_id,
    owner_id=verified_owner_id,
    checkpoint_id=current.checkpoint_id,
)
```

retry continues the incomplete graph step once; it has no retry loop. It cannot approve
a waiting review or restart a completed graph. The backend must classify failures, enforce
delays/attempt limits and retain the job's outcome. Checkpoints do not guarantee exactly-once
model billing after a crash between provider response and checkpoint commit.

| AIError code | Meaning |
| --- | --- |
| workflow_not_found | Missing workflow or owner mismatch; do not disclose which |
| workflow_exists | Owned workflow ID already exists; inspect it instead of restarting |
| stale_workflow | Checkpoint/action changed; return a conflict and reload the prompt |
| invalid_workflow_reply | Answer does not match the current action's schema |
| workflow_not_waiting | No pending action accepts a reply |
| workflow_not_retryable | The graph is waiting for user input or already complete |
| provider_error / provider_unavailable | Provider failure; consult retryable and the job budget |
| other AIError | Translate into your shared error contract; never fabricate a success result |

Sanitize backend/database/Pydantic errors as well. Production locking, job atomicity,
PostgreSQL provisioning/ownership isolation and end-to-end integration remain backend
verification tasks. This handoff has been tested with isolated adapters and local durable
SQLite checkpoints; no live paid Gemini calls or remote database changes were made.
