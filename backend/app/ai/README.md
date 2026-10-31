# CivicMesh AI — first implementation milestone

Work branch: `feat/ai-workflow`. This module implements text extraction and a
checkpointed clarification/review workflow. It does not implement frontend,
API routes, database persistence or a job worker.

## What works

- Configurable Gemini adapter using `google-genai`; no model identifier default.
- Pydantic validation of inputs and model responses, bounded text and answer history.
- Unknown observations stay null. Model outputs cannot contain official status,
  receipts, authenticated IDs or confirmed coordinates.
- LangGraph extraction -> missing information -> clarification -> re-extraction.
- Original report text remains unchanged; answers are stored separately.
- At most three clarification rounds (four extraction calls including the initial call).
- Explicit human review before `ready_for_backend`; rejection produces `rejected`.
- Remaining missing information after the limit produces `needs_information`.
- Required injected checkpoint saver. No implicit in-memory production fallback.
- Sanitized provider errors and a CLI for explicitly authorized live text extraction.
- Backend matching/official-source interfaces, ready for teammate coordination.

Approval sends no complaint, merges no incident and changes no authority status.
Authority status in the result is always `unknown`.

## Windows setup

From the repository root:

```powershell
git branch --show-current
Set-Location backend/app/ai
uv sync --frozen --python 3.11
uv run --frozen ruff check .
uv run --frozen pytest -q
uv run --frozen civicmesh-extract --help
```

The isolated project installs as `civicmesh_ai`. Its own pyproject and uv.lock
avoid choosing the backend teammate's dependency structure. At integration,
the backend can install this local package or coordinate moving its dependencies
into the backend's shared manifest. Do not independently create conflicting schemas.

## Live extraction

Set `GEMINI_API_KEY` and `GEMINI_MODEL` in the process environment. Use a model
available to your project that supports structured output. `.env.example` lists
the variables; this module does not automatically read `.env` files.
Keep keys in your local environment or secret manager, never in Git or chat.

Put a genuine, consented UTF-8 report in an ignored `private-inputs/` folder:

```powershell
uv run --frozen civicmesh-extract --text-file private-inputs/report.txt --allow-paid-call
```

This sends the report to Gemini and may incur charges. Without the flag the CLI
refuses to call the provider. The CLI performs extraction only; it does not create
reports, jobs or checkpoints. It prints the extraction to your terminal, so treat
that terminal output as private citizen data. Do not attach private reports to PRs.

No live paid call was made while implementing or testing this milestone.

## Backend integration contract

Import the library through its installed package:

```python
from civicmesh_ai.graph.workflow import build_workflow, initial_state
from civicmesh_ai.providers.gemini import GeminiProvider
from civicmesh_ai.schemas import ReportInput
from langgraph.types import Command

# These values must come from the authenticated backend/worker, not model output.
provider = GeminiProvider.from_environment()
graph = build_workflow(provider, checkpointer=backend_checkpoint_saver)
config = {"configurable": {"thread_id": persisted_workflow_thread_id}}
state = initial_state(ReportInput.model_validate(stored_report_payload))
paused_or_done = await graph.ainvoke(state, config)

# After authorizing the answer and validating it as Clarification or ReviewDecision:
resumed = await graph.ainvoke(Command(resume=validated_answer), config)
# Close provider resources during worker shutdown:
await provider.close()
```

The snippet is an integration outline, not a standalone executable script. The
backend supplies `backend_checkpoint_saver`, the persisted thread identifier,
stored report payload and authorized resume data.

Initial report fields: `report_id`, `text`, optional `category`, optional `location`.
Location fields: `latitude`, `longitude`, `confirmed: true`.
Model input excludes report IDs and confirmed coordinates. Citizen text itself
may contain personal information; consent/redaction policies remain backend concerns.

With `ainvoke`, an interrupt is returned under `__interrupt__`. Each interrupt
value contains a kind: `clarification` or `extraction_review`. Clarification includes
field names and questions. Review includes the extraction and effective location/category.
The backend must return these only to the authorized owner/reviewer.

Clarification reply: optional `text`, `category`, `location`, with at least one
nonempty answer. Review reply: `{"approved": true}` or `{"approved": false}`.
Validation rejects extra fields. A human-selected category conflicting with the
extraction triggers clarification; a selected category cannot alone make unrelated
model output in-scope. Final output is under `result` and follows `ExtractionResult`.

Backend responsibilities before production integration:

1. Verify identity and ownership before starting, reading or resuming a thread.
   Thread IDs are not authorization. Never expose arbitrary graph state updates.
2. Persist a unique thread ID with each workflow run; do not reuse finished threads
   for new reports. Serialize resumes and reject stale/repeated answers at the API layer.
3. Supply an initialized durable PostgreSQL checkpointer and test process restarts.
   Tests here use memory only and do not establish production durability.
4. Run the graph in a worker, persist job transitions and result ownership, and apply
   bounded persistent retries only when appropriate. This module does not provide
   exactly-once execution or crash-safe paid-call deduplication.
5. Translate `AIError.code` and `retryable` into the shared error/job contract. Do not
   return raw validation errors, provider payloads or checkpoint content to clients.
6. Treat saved state as private. Define encryption, retention and deletion policies.
   Keep remote tracing off unless explicitly approved for private citizen data.

## Verification and limits

Implementation checks on Python 3.11: 34 tests passed; Ruff lint and import/bytecode
checks passed. The real SDK's JSON/schema conversion is also exercised through an
isolated local HTTP transport, with no external request.

Tests use isolated provider doubles, never operational/demo data or runtime fallbacks.
They exercise interrupt/resume behavior, bounded clarification, category conflicts,
separate thread state, invalid answers, schema constraints, SDK request construction,
sanitized failures, and the CLI paid-call gate.

Prompt-injection tests verify instruction/data separation and prohibited output
fields. They do not prove that a live model resists every injection. Model summaries
still require review, and the model has no tools or permission-setting ability.

Not implemented in this milestone: photo/audio ingestion, priority assessment,
matching integration, authority retrieval, complaint generation, follow-up assessment,
durable PostgreSQL checkpoint wiring or frontend/API integration. These are subsequent
AI milestones requiring backend contracts and genuine evidence; no dummy outputs exist.

References used for the adapter and workflow:
- [Google Gen AI SDK](https://googleapis.github.io/python-genai/)
- [Structured output](https://ai.google.dev/gemini-api/docs/structured-output)
- [LangGraph interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)
- [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence)
