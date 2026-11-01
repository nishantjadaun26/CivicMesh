# CivicMesh deployment and operations runbook

This is an owner-executed plan. No production database, deployment, account setting
or paid resource was changed by the integration task. Complete staging first.
Use [the environment inventory](environment.md) for every variable and
[the integration audit](integration-audit.md) for verification and remaining limits.

## 1. Architecture, accounts and deployment order

The repository implements a React/Vite static SPA, a Python 3.11 FastAPI API, a
separate continuously running Python worker, Supabase Auth/private Storage, and
PostgreSQL with PostGIS. Jobs live in PostgreSQL; LangGraph checkpoints live in a
private schema in that same logical database. No Redis or Vercel background worker
is required. The existing vector extension/column is retained by the initial
migration but no embedding service is called.

Use separate staging and production Supabase projects and host environments. The
following concrete hosting split is compatible: Vercel for `frontend/`, and a
Docker web service plus Docker background worker on Render. The background worker
is a persistent service, not a serverless request handler. Review the selected
host plans and costs before the owner creates resources; this runbook promises
no free hosting or zero-cost model calls. [Render worker model](https://render.com/docs/background-workers)

Order: approve code/CI → configure staging database/Auth/Storage → apply staging
migrations and provision checkpoints → start worker → start API → configure
frontend and exact CORS/Auth URLs → complete staging smoke checks → owner approves
the equivalent production rollout. Keep automatic production deployment disabled
until that approval.

## 2. Local preparation and tests

Install Git, Python 3.11, uv 0.8.15, Node 24 and Docker if running the database or
container checks locally. From the repository root:

```powershell
git switch feat/project-integration
git pull --ff-only
uv sync --project backend --frozen --extra dev
backend/.venv/Scripts/ruff.exe check backend scripts
backend/.venv/Scripts/pytest.exe -q backend/tests backend/app/ai/tests
backend/.venv/Scripts/python.exe scripts/validate_migrations.py
backend/.venv/Scripts/python.exe scripts/export_openapi.py
git diff --exit-code contracts/openapi.json
```

On Linux replace `backend/.venv/Scripts/` with `backend/.venv/bin/`. For frontend:

```powershell
Set-Location frontend
npm.cmd ci
npm.cmd run api:generate
git diff --exit-code src/types/api.generated.ts
npm.cmd run typecheck
npm.cmd run build
npm.cmd test
npm.cmd run test:integration
npm.cmd audit --audit-level=moderate
```

Use `npm` instead of `npm.cmd` on Linux. Local Windows browser tests use installed
Edge; CI installs Chromium with `npx playwright install --with-deps chromium`.
The backend CI independently provisions a disposable PostgreSQL database and
builds/import-checks the production container. Browser harness providers/storage
are confined to test files and never shipped in the Docker image. There is no
separate frontend ESLint or backend type-check configuration; do not label
TypeScript compilation or Ruff as a nonexistent check.

For genuine local development, copy `backend/.env.example` to repository-root
`.env` and `frontend/.env.example` to `frontend/.env.local`, then fill real local
or staging values privately. Prepare the database as below, then run in separate
shells from the repository root:

```powershell
backend/.venv/Scripts/uvicorn.exe backend.app.main:app --host 127.0.0.1 --port 8000 --no-access-log
backend/.venv/Scripts/python.exe -m backend.app.worker
```

In `frontend/`, run `npm.cmd run dev`. A worker with configured real credentials
will call Gemini when genuine jobs are queued; offline tests do not start that
worker. SQLite checkpoints are only for local single-process development.

## 3. Staging Supabase/database setup

1. The owner creates or selects a staging project, records the real pilot
   jurisdiction/center and chooses a region near the API/worker. Obtain the URL,
   browser publishable/anon key, server service_role JWT and database connection
   details. Keep production credentials out of staging and PR previews.
2. Confirm `uuid-ossp`, PostGIS and vector are available through the dashboard's
   database extension controls. Their creation appears in migration 1; the owner
   must resolve permission issues rather than removing the extensions or security
   policies to make migration execution pass.
3. Install the Supabase CLI. If this checkout has no `supabase/config.toml`, run
   `supabase init`, review its generated local settings and disable any generated
   seed-file setting before a local reset. The repository supplies no operational
   seed data. Link **staging** interactively; do not pass passwords in committed
   commands. Review migration history before pushing:

   ```text
   supabase login
   supabase link --project-ref <staging-project-ref>
   supabase migration list
   supabase db push --dry-run
   supabase db push
   supabase migration list
   ```

   Apply `20261101000000_initial_schema.sql` before
   `20261101010000_integrated_workflows.sql`. If an initial schema was applied
   manually, reconcile its history with the actual tables before running the
   second migration; do not blindly rerun policy creation or mark unapplied SQL
   as applied. Migration 2 refuses duplicate jobs instead of discarding them.
   [Supabase migration workflow](https://supabase.com/docs/guides/deployment/database-migrations)

4. Configure the API/worker environment using the inventory. Keep the supplied
   `civicmesh-evidence` bucket private, with 10 MiB per-file limit and the listed
   JPEG/PNG/WebP/audio MIME types. Owner reads require verified, owner-bound
   evidence. Unmoderated report and follow-up content must stay private.
   [Storage access controls](https://supabase.com/docs/guides/storage/security/access-control)
   Download the project's CA certificate from Database Settings → SSL Configuration
   when required, mount it as a host-provided file on API and worker, and set
   `DATABASE_SSL_ROOT_CERT` to that path. Both drivers verify certificates and
   hostnames; do not bypass verification to work around a missing CA. Choose the
   matching project's certificate and test the actual connection in staging.
   [Supabase SSL verification](https://supabase.com/docs/guides/platform/ssl-enforcement)
5. Provision private LangGraph tables once, explicitly, using a secure owner shell
   with the **staging** checkpoint DSN. The first command makes no connection:

   ```powershell
   backend/.venv/Scripts/python.exe -m backend.app.worker.init_checkpoints
   backend/.venv/Scripts/python.exe -m backend.app.worker.init_checkpoints --apply
   ```

   The worker never runs schema setup automatically. Check that checkpoint tables
   are in `civicmesh_checkpoints`, and that `anon`, `authenticated` and
   `service_role` cannot use that schema. Do not add it to Supabase's exposed API
   schemas. The database role used by the worker must retain access.
   [LangGraph checkpoint persistence](https://docs.langchain.com/oss/python/langgraph/persistence)
6. In Supabase Authentication → URL configuration, set the real staging frontend
   Site URL and approved redirect URL ending in `/profile`. Add local URLs only
   for development and exact preview origins only when needed. Use production
   URLs in the production project. Confirm email-signup/confirmation behavior in
   staging; no custom SMTP service is implemented in this repository.
   [Auth redirect configuration](https://supabase.com/docs/guides/auth/redirect-urls)
7. Prefer asymmetric project signing keys. The API obtains ES256/RS256 public keys
   from the configured project's JWKS endpoint, validates issuer, audience, expiry,
   subject and citizen role. Legacy HS256 requires the separate server JWT secret.
   Allow the documented key-cache propagation period during rotation; never
   replace verification with an unverified JWT decode. [Supabase JWT verification](https://supabase.com/docs/guides/auth/jwts)

Before a production migration, separately obtain owner authorization, a database
backup/restore plan and a maintenance window for constraint validation. Store
Storage object backups as well: database backups do not contain uploaded files.
Verify the available backup features for the actual plan and test a restore.
[Supabase backup scope](https://supabase.com/docs/guides/platform/backups)

## 4. Worker and API hosting

Use the repository root as Docker build context and `Dockerfile` as its path.
The image installs the backend and local AI package from the frozen backend lock,
runs as an unprivileged user and excludes test/private-input/env files. Verify the
same reviewed commit on both services. [Docker deployment on Render](https://render.com/docs/docker)

For the **worker**, create a background-worker service, select Docker, and override
the image command with:

```text
python -m backend.app.worker
```

Set all shared runtime settings and the worker-only Gemini/checkpoint values in
its environment dashboard. Use direct or session database connections, with TLS,
for both DSNs. Never use a transaction pooler for session advisory locks. One worker
holds an application database session lock, a job database session and a separate
checkpoint connection while processing; budget connections before scaling.

Start with one worker instance and one sequential execution per instance. Additional
instances coordinate with PostgreSQL exclusion, not in-memory locks. A crash or
timeout consumes a persisted failure budget; the default stale lease is ten
minutes. Waiting for user input is a persisted state and does not require a worker
to hold a job indefinitely. No persistent filesystem volume is needed for
production checkpoints because they are stored in PostgreSQL.

For the **API**, create a Docker web service from the same commit. The image's
default command is:

```text
uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8000} --no-access-log
```

The host provides `PORT` if necessary. Set the API runtime environment, exact
frontend CORS origins and Storage/Auth credentials. Gemini credentials are needed
only on the worker. Set the web service's HTTP health path to `/health/ready`.
Deploy the initialized worker first so its heartbeat can satisfy API readiness.
[Render HTTP health checks](https://render.com/docs/health-checks)

`/health/live` tests process liveness only. `/health` reports configuration,
database schema connectivity and readiness; `/health/ready` returns 503 without a
recent initialized-worker heartbeat. Heartbeats are not proof of valid model
credentials, quota or a successful genuine report. Monitor both API health and
worker logs separately. Errors log type and job/request reference without model
responses, report text, keys, DSNs or signed URLs. Do not turn on external provider
HTTP body logging in production.

## 5. Vercel frontend

1. Import `nishantjadaun26/CivicMesh`, select the reviewed branch/commit for staging,
   set **Root Directory** to `frontend`, Framework Preset to **Vite**, Node to **24**,
   Install Command to `npm ci`, Build Command to `npm run build` and Output
   Directory to `dist`. This is a static SPA; the repository does not contain a
   Next.js server. `frontend/vercel.json` provides deep-link rewrites and headers.
   [Vite deployment settings](https://vercel.com/docs/frameworks/frontend/vite)
2. Add the five `VITE_` variables from the inventory to the appropriate Preview or
   Production environment. Set `VITE_API_URL` to the actual HTTPS API origin,
   without `/api`. Do not upload `.env`, a service_role key, database DSN or Gemini
   key to the frontend. Build validation rejects obvious server-key exposure.
3. Redeploy after changes to public variables. Inspect the resulting bundle for
   server-only values before approving a production build. Give preview builds a
   staging backend/project and explicit preview CORS/Auth redirect entries.
4. Add the owner-controlled domain in Vercel's domain settings, follow the displayed
   DNS records, wait for HTTPS to validate, and then update the API's exact CORS
   origin and Supabase Site URL/redirect list. Recheck sign-in after changing domains.

The browser calls the separate HTTPS API directly with a bearer token and
`credentials: omit`; no shared-domain cookies or API proxy rewrite is required.
Only SPA page routes rewrite to `index.html`. Do not point API requests at that
rewrite or expose the API as a short-lived Vercel worker.

## 6. External services and verified sources

Set the worker's genuine API key and explicit supported model ID. Inspect the
project's current rate limits, quota and billing in AI Studio before owner-approved
live verification. The SDK performs one request per operation; the persisted job
budget controls retries. Extraction, priority, routing and complaint drafting can
each require calls, and crashes between a response and checkpoint commit can
repeat a billable request. No zero-cost or exactly-once billing claim is made.
[Gemini rate limits](https://ai.google.dev/gemini-api/docs/rate-limits)

Choose a map/tile provider authorized for the intended traffic, configure its
template and required attribution, restrict any public browser token by origin,
and test errors on mobile. Blank map configuration leaves incident lists and
manual coordinates available. If choosing OSM's public tiles, follow its usage
policy; no production SLA is implied. [OSM tile policy](https://operations.osmfoundation.org/policies/tiles/)

Routing requires real owner-verified official passages whose jurisdiction exactly
matches the configured pilot and whose location is within its radius. The code
ships no authority catalog. First check the domain's authenticity and the passage's
meaning, then save the exact approved passage in a private local UTF-8 file. For
HTML/text sources, the owner can run:

```text
python scripts/ingest_official_source.py --authority "<verified authority name>" --jurisdiction "<exact pilot jurisdiction>" --title "<real document title>" --url "<official HTTPS document URL>" --passage-file "<private passage file>" --verified-official
```

That command is plan-only. Add `--apply` only when authorized to fetch the source
and write to the configured staging database. The command bounds the fetch,
rejects private/rebound/redirected internal destinations, verifies that the exact
passage appears in the fetched text and stores provenance/hash/timestamps. It does
not prove that an arbitrary domain is official; human verification is mandatory.
PDF/OCR ingestion is not implemented. Reverify and retire superseded sources
through an owner-reviewed catalog maintenance process. Missing routing sources
produce `authority_unavailable`, not a guessed recipient or complaint receipt.

## 7. Staging smoke checks and evidence

Record actual outcomes and request/job IDs privately; never fill this checklist
with invented success. The owner or backend teammate must use a genuine,
non-sensitive observation in the agreed staging locality for provider verification.

| Check | Required evidence |
|---|---|
| Liveness/readiness | `/health/live` 200; `/health/ready` 200 with database connected and recent worker heartbeat; stopping worker eventually yields 503 |
| Auth | Real sign-up/confirmation/sign-in/sign-out; browser contains only public keys; signed-out private pages hide data |
| Private upload | Authorized ticket, successful upload, size/type/hash verification; object URL without authorization unavailable; another account cannot bind/read it |
| Idempotency | Retry the same payload/key after an uncertain response; exactly one report/job; changed payload/key reuse rejected |
| Processing | A genuine queued report reaches worker; inspect actual model-derived extraction and uncertainties; do not confuse `pending` with success |
| Clarification | Missing information pauses; provide the displayed checkpoint/action reply; original observation remains unchanged; stale/other-owner replies fail |
| Reviews | Explicit extraction and complaint/follow-up approvals; no automatic complaint submission or official-status change |
| Persistence | Restart worker between stages; reload private report; result and review state survive |
| Failures | Missing/invalid provider config and quota/network failures remain truthful, sanitized and bounded; no local-success fallback |
| Public projection | Public incident endpoints expose approved projections only; no private citizen text, media paths, raw checkpoints or identity leaks |
| Follow-up | Fresh same-location photo creates a private job; absent authorized baseline returns insufficient evidence; official status remains unchanged |
| Browser/deployment | Direct deep links work, HTTPS/CORS match, mobile layout works, configured tile attribution visible, no server credentials in bundles |

There is no automatic report-to-public-incident publication or merge. Existing
public incident views require actual moderated records. If no such records exist,
the correct incident screen is empty. Campaigns, support, badges and rewards are
outside the implemented pilot and remain unavailable. Do not manufacture records
to make smoke screenshots look populated.

For staging cleanup, pause only staging workers, collect the exact test report/job
and storage object IDs, and remove the selected objects through the Storage owner
dashboard. Then remove associated private checkpoints using the installed saver
thread-deletion API for `civicmesh:<job_id>`, and delete only the selected staging
report/follow-up rows after inspecting their cascades. Remove the staging test
account only if it owns no real data. There is no bulk-delete application endpoint;
the owner must approve the exact cleanup targets. Never use a production project
or an unqualified table-wide delete for this procedure.

## 8. Rollback and operations

- Keep the previous known-good API/worker image/commit and Vercel deployment.
  Revert frontend and services through their deployment history or redeploy that
  exact commit. Roll back API and worker together when contracts change; do not
  assume a previous frontend understands new workflow payloads.
- Pause worker intake before a schema-affecting rollback. Graceful SIGTERM lets
  the current bounded slice finish; configure a platform grace period accordingly.
  If the host terminates it sooner, the PostgreSQL session lock releases and the
  stale-lease recovery path applies. Never run an old worker against an
  incompatible checkpoint schema.
- Migrations are not safely undone by rolling back code. Prefer a reviewed forward
  fix; restore backups into an isolated project to assess recovery. Restore jobs,
  checkpoints and object metadata consistently, and recover Storage objects from
  their separate backup. Take another backup before any corrective data operation.
- A stuck `running` job becomes eligible after its lease expires, but only a
  worker that acquires its workflow exclusion may recover it. A `waiting_for_input`
  job needs the owner's saved prompt reply. Exhausted/invalid-output jobs stay
  failed; investigate configuration/evidence and retain their audit history.
  Never blindly clear retry counts or replay a stale human approval. Missing
  saved checkpoints fail for operator recovery rather than silently restarting.
- Alert on failed readiness, missing worker heartbeats, old pending/running jobs,
  terminal failures and sustained provider/rate-limit errors. Protect dashboards
  containing job IDs and report contents. Use aggregate counts for public metrics.
- Rotate leaked credentials at their provider, restart affected services, invalidate
  compromised Auth sessions where appropriate and follow Supabase's signing-key
  rotation procedure. Check logs, bundles, repository history and shared artifacts
  for exposure without copying secret values into tickets or chat.
- Review data retention with the pilot owner. Private checkpoints contain original
  reports and answer history even after a UI result is complete. Account/report
  database cascades alone do not remove separate checkpoint threads or Storage
  files; include all three in a verified retention/erasure procedure.

## 9. Go-live gate

Every item below must have a recorded pass; unchecked items mean production is
not approved. The integration task does not grant deployment/migration authority.

- [ ] Integration PR reviewed and all required CI checks pass on its final head.
- [ ] Staging migrations, indexes, RLS, private Storage and checkpoint access verified.
- [ ] Real project JWT signing mode and browser/server key boundaries verified.
- [ ] Genuine provider report, clarification, reviews and restart smoke checks pass.
- [ ] Exact production URLs, pilot coordinates, source catalog and map terms approved.
- [ ] Monitoring, quotas, secret ownership, backups, retention and restore test assigned.
- [ ] Rollback commits and compatibility reviewed; workers use session/direct DB connections.
- [ ] Owner explicitly authorizes the production migration, resource creation and deployment.

Until those owner-operated checks pass, the appropriate verdict is **ready for
staging setup and verification, not approved for production**.
