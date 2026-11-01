# CivicMesh

Three-person hackathon project with separate citizen frontend, backend and AI modules.
The modules have their own checks; connecting them into a working application is the
next integration milestone. See [merge review and integration handoff](docs/merge-review.md).

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

The backend exports `contracts/openapi.json`. The frontend must still be adapted to
that contract. See [frontend setup](frontend/README.md) and [AI setup](backend/app/ai/README.md).

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
