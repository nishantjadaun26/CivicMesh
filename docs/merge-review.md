# Module review and integration handoff

Reviewed on 2026-11-01: AI PR #1, backend PR #2 and frontend PR #3.
These branches can coexist without merge conflicts. Merging the modules does not
establish an operational end-to-end application.

## Review corrections

- Backend authentication rejects placeholder secrets and checks JWT audience, issuer,
  expiry and role. Its current adapter supports legacy Supabase HS256 tokens only.
- Upload tickets require successful private-storage signing. Evidence binding verifies
  uploaded object size, MIME header, signature and SHA-256 before accepting it.
- Public timelines exclude unmoderated citizen/AI payloads; private incidents cannot
  receive public follow-ups. Raw timeline rows and evidence remain private through RLS.
- Report idempotency rejects changed payloads. Clarification preserves the original
  observation and stores the reply separately for a future worker consumer.
- Official-source HTTP requests pin the validated public IP, retain TLS hostname
  verification and validate each redirect. Matching excludes private incidents.
- Frontend operational seed data, fake identities/rewards and local-success fallbacks
  were removed. Missing services and incompatible response shapes fail explicitly.
  Coordinates require explicit confirmation; map tiles require configured attribution.
- Frontend CI now runs type checking, production build and headless browser tests.

## Validation

An isolated checkout combining all three reviewed branches passed 122 Python tests
(31 backend, 91 AI), Ruff and an unchanged OpenAPI export. The frontend passed
TypeScript checking, production build and six browser tests covering empty/error
states, legacy cache isolation, location confirmation, submission failure and responsive
layouts. These checks use isolated test fixtures, not live citizen reports.

PostgreSQL/Supabase migrations, RLS and PostGIS were not exercised against a live
database. No migration was applied, external model calls made or deployment performed.
SQLite unit tests do not establish production database correctness or concurrency.

## Next milestone: whole-project integration

1. Resolve the frontend framework decision: the implemented frontend is React/Vite,
   while the original proposal requested Next.js. Preserve the current UI during review;
   any migration belongs in the integration plan.
2. Generate frontend types from OpenAPI and align upload, report, job, incident,
   clarification and follow-up paths and DTOs. Current frontend service adapters use
   different shapes and are intentionally not described as connected.
3. Wire the backend worker to the installed `civicmesh_ai` package and its typed
   coordinator. Provide authorized media bytes and source/matching adapters, durable
   checkpoints, clarification resume handling, human review and real job polling.
4. Validate migrations and ORM alignment in a disposable Supabase/PostgreSQL environment,
   including RLS, private storage, geographic queries and concurrent job/idempotency behavior.
5. Configure real auth, explicit CORS origins, pilot locality, approved official sources
   and map provider/attribution. Add JWKS auth support if the Supabase project uses
   asymmetric signing keys. Keep service-role keys exclusively on the backend.
6. Connect account-scoped report history and clear private session state on auth changes.
   Campaigns, support and rewards have no completed backend service; keep them unavailable
   or agree their scope rather than inventing local success.
7. Run authenticated end-to-end flows and the backend teammate's live Gemini verification
   using locally configured credentials and a genuine non-sensitive observation. The AI
   README contains offline preflight and live-verification instructions. Paid calls
   are not authorized by this merge task.

Do not expose unreviewed observations publicly or turn AI/citizen observations into
official authority status. Complaint packets remain drafts; no automatic submission
or official receipt is implemented.
