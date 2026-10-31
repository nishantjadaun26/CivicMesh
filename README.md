# CivicMesh

Shared citizen evidence for garbage accumulation and water leaks in one locality.
This repository contains the **foundation, not a working reporting product**.
No operational data, government acknowledgements, AI results or metrics are fabricated.

Start with [Windows setup](docs/setup.md), [architecture](docs/architecture.md),
[API contracts](docs/api-contracts.md), and [team ownership](docs/team-ownership.md).

| Area | Working foundation | Remaining implementation |
|---|---|---|
| Frontend | Responsive Next.js shell; report/incident/detail/sign-in pages; media selection, recording, manual location; typed API client | Clarification/timeline/follow-up flows, session UX, end-to-end report results |
| API | Validated contracts, request IDs, errors, explicit CORS, Supabase token verification adapter, liveness | Owner-authorized repositories, actual submissions and upload signing |
| Database | 11 SQLAlchemy models, PostGIS/pgvector migration, private access policies, public projection | Apply and test against local Supabase; production role provisioning |
| AI | Typed state, Gemini schema validation, tool boundaries, LangGraph builder, review interrupts | Multimodal ingestion, priority, source-backed complaints, follow-up assessment |
| Jobs | Persistent schema, leasing/retry interfaces, fail-closed worker entry point | Durable queue adapter, checkpoint saver and crash/retry testing |
| Review | CI, PR template, schema-validated CodeRabbit configuration | Owner activation if needed; observe first genuine PR review |

`GET /health` returns liveness with `ready: false`. Other endpoints return honest
401, 422, 503 or 501 errors until their dependencies and implementations exist.
Neither selecting credentials nor setting a model name enables missing persistence.

The shared foundation is integrated on `main`. Team branches start at the same commit:
`feat/frontend`, `feat/ai-workflow`, `feat/backend`. See [Git workflow](docs/git-workflow.md)
and [CodeRabbit review](docs/code-review.md).

No paid services are created by this setup. Deployment configuration is a template;
see [deployment](docs/deployment.md). [Verification](docs/verification.md) records limits.
