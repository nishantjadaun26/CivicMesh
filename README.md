# CivicMesh

Folder structure and CodeRabbit setup for our three-person hackathon team.
Application code, dependencies, API contracts, database migrations and deployment
configuration are left for the team to implement.

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

Empty folders use `.gitkeep` so Git tracks them. Generate `contracts/openapi.json`
as a file when the backend contract is implemented; it is not pre-created here.

| Teammate | Branch | Module |
|---|---|---|
| 1 | feat/frontend | Frontend |
| 2 | feat/ai-workflow | AI workflow |
| 3 | feat/backend | Backend and Supabase |

`main` is the integration branch. All branches share the trimmed setup.
See [team ownership](docs/team-ownership.md) and [Git workflow](docs/git-workflow.md).

CodeRabbit configuration, schema-validation CI and the PR template are included.
GitHub App activation is **unverified**; no actual PR review has been observed.
See [activation and review instructions](docs/code-review.md).
