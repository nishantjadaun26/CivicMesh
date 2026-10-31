# Team ownership

| Teammate | Branch | Owned paths |
|---|---|---|
| 1 | feat/frontend | frontend/ |
| 2 | feat/ai-workflow | backend/app/ai/ |
| 3 | feat/backend | backend/app/api/, backend/app/database/, backend/app/services/, backend/app/worker/, supabase/ |

Coordinate future shared schemas, API contracts, dependency files, migrations,
deployment and CI changes before editing. No teammate GitHub usernames are assumed.

This setup contains folders and review configuration only. Each teammate implements
their module through small PRs into main, with CodeRabbit feedback and human review.
