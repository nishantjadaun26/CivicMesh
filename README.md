# CivicMesh

Three-person hackathon project with separate citizen frontend, backend and AI modules.
The React/Vite frontend now connects to FastAPI uploads, private reports and persistent
AI worker jobs. Clarification and human reviews resume durable LangGraph workflows.
Real staging credentials and owner-run deployment verification are still required.

- [Architecture, audit and readiness](docs/integration-audit.md)
- [Environment variables](docs/environment.md)
- [Ordered deployment and operations runbook](docs/deployment-runbook.md)
- [Verification commands and results](docs/verification.md)

```text
frontend/src/
  app/
  components/
  features/{reports,incidents,auth}/
  lib/{api,supabase}/
  types/
backend/
  app/
    api/{routes,dependencies}/
    core/
    schemas/
    database/{models,repositories}/
    services/{reports,incidents,matching,routing,storage,jobs}/
    ai/{graph,nodes,tools,prompts,providers}/
    worker/
  tests/
supabase/migrations/
contracts/examples/
docs/
.github/workflows/
```

The backend exports `contracts/openapi.json`; frontend API types are generated from
it. See [frontend setup](frontend/README.md), [backend setup](backend/README.md) and
[AI package setup](backend/app/ai/README.md).

| Teammate | Branch | Module |
|---|---|---|
| 1 | feat/frontend | Frontend |
| 2 | feat/ai-workflow | AI workflow |
| 3 | feat/backend | Backend and Supabase |

`main` is the integration branch. Keep feature branches for subsequent team work.
See [team ownership](docs/team-ownership.md) and [Git workflow](docs/git-workflow.md).

CodeRabbit configuration, schema-validation CI and the PR template are included.
The GitHub App has posted real reviews on this repository's implementation PRs.
See [activation and review instructions](docs/code-review.md).
