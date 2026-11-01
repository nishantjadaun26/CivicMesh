# Integration verification

The authoritative final-head CI results are attached to
[integration PR #4](https://github.com/nishantjadaun26/CivicMesh/pull/4).
Local checks use Python 3.11 / uv 0.8.15 and Node 24. No owner production database,
genuine model request or deployed site was used.

| Command / check | Outcome |
|---|---|
| `uv sync --project backend --frozen --extra dev` | Passed; locked local backend and AI package installed, including psycopg binary |
| `backend/.venv/Scripts/ruff.exe check backend scripts` | Passed locally; same check in Linux CI |
| `backend/.venv/Scripts/pytest.exe -q backend/tests backend/app/ai/tests` | 140 passed, 1 PostgreSQL test skipped locally because PostgreSQL/Docker are unavailable on this machine |
| `backend/.venv/Scripts/python.exe scripts/validate_migrations.py` | Both migrations parse: 54 and 39 SQL statements |
| `backend/.venv/Scripts/python.exe scripts/export_openapi.py` then `git diff --exit-code contracts/openapi.json` | Export/type changes regenerated and checked; final tracked schema must remain unchanged on re-export |
| `npm.cmd ci` in frontend | Passed; lockfile installs without forced peers |
| `npm.cmd run api:generate` then `git diff --exit-code src/types/api.generated.ts` | Types generated from current OpenAPI; drift compared in CI |
| `npm.cmd run typecheck` | Passed |
| `npm.cmd run build` | Passed; Vite production bundle |
| `npm.cmd test` | Service-state suite covers unavailable services, legacy caches, no fake identity, real coordinate selection, no false submission and mobile layouts; final CI runs all seven cases |
| `npm.cmd run test:integration` | Real browser→API→ORM→worker→LangGraph→checkpoint→UI flow passes; provider/Auth/Storage doubles exist only in tests |
| `npm.cmd audit --audit-level=moderate` | Zero vulnerabilities after the patched minimatch override |
| `backend/.venv/Scripts/python.exe scripts/check_public_bundle.py` after build | Passed; checked server variable names, any configured process-secret values and the browser-test signing fixture are absent from SPA assets |
| `pytest -q backend/tests/test_postgres_integration.py` with the CI-only loopback DSN | Passed in disposable PostgreSQL CI: SQL migrations, RLS/Storage policies, PostGIS coordinates, idempotency race, real worker/checkpoints and session exclusion |
| `docker build -t civicmesh-check .` and runtime import/excluded-test check | Passed in Linux container CI; Docker is unavailable locally |
| `python -m backend.app.worker.init_checkpoints` without `--apply` | Plan-only behavior verified; no network/database operation |
| Genuine Supabase Auth/Storage, Gemini quota/model/media and deployed HTTPS/CORS smoke checks | Not run; require owner-controlled staging credentials, genuine report and explicit deployment/live-verification authorization |

Linux executables are under `backend/.venv/bin/`. The CI backend test job skips its
database-only case, then a separate disposable PostgreSQL job executes that case.
Windows browser test cases reported passes, but the managed shell's subprocess
cleanup needed interruption; the complete browser commands are verified to exit
successfully in Linux CI. That limitation is not presented as a clean Windows CLI
exit. No separate frontend ESLint or backend type checker is configured.

Meaningful added regressions cover duplicate/stale replies, private results,
clarification across checkpoint reopen, two human review stages, failure backoff
and exhaustion, overlapping workers, crashed leases, a failed result commit,
lost checkpoint refusal, JWT JWKS issuer isolation, shared write limits, readiness,
JSON size limits, startup secret redaction, environment-doc drift and source
passage authenticity. Existing 91 AI tests cover extraction schemas, SDK failure
and invalid outputs, prompt-injection boundaries, bounded clarification, genuine
citations, insufficient media and durable workflow state.

Verdict: **ready for owner-operated staging setup and smoke verification; not
approved for production**. The [runbook](deployment-runbook.md) lists the external
prerequisites, ordered steps, smoke gates, rollback and cleanup.
