# Foundation verification

Local checks run on Windows, Python 3.11 and Node 24:

- Backend imports and FastAPI startup; pytest: 20 passing tests.
- Schema bounds, required location confirmation, upload constraints, private-route rejection,
  configured Auth verification via isolated transport doubles, sanitized errors and honest 501/503 states.
- LangGraph compilation with an explicit test-only memory saver and unknown-information behavior.
- Ruff lint; OpenAPI regenerated and checked; frontend types regenerated from it.
- Frontend ESLint, TypeScript checking and Next.js production build.
- Live local HTTP smoke checks: API /health and /openapi.json, frontend /, /reports,
  /incidents and /auth all returned 200. Health correctly reported ready=false.
- CodeRabbit YAML validated against the downloaded official schema.
- SQLAlchemy PostgreSQL DDL generated and checked against all model/policy sources.

Limitations: no local PostgreSQL or Docker executable was available. Migration execution,
extension compatibility, RLS enforcement and Storage behavior remain unverified. No remote
database was changed. No real Supabase account/token, Gemini request or official authority
submission was used. Durable queue/checkpoint execution remains unwired; worker exits 78.
No interactive browser QA, device recording test or live map-provider test was performed.
Production build success does not establish those behaviors.

`npm audit --omit=dev` reports zero vulnerabilities. The complete install reports 18 moderate
development-tool findings in lint/type-generation dependency chains (including minimatch).
Some proposed fixes are incompatible major downgrades. No force downgrade was applied;
reassess upstream ESLint/Next lint/openapi-typescript compatibility before upgrading. These
tools still process PR code in CI, so use no production secrets and keep workflow permissions read-only.

CodeRabbit integration is unverified: a repository installation probe returned 404; the user
installation API returned 403 because it requires a GitHub-App-authorized token. Repository
read/push access works. No PR existed during setup and no real review was observed.
