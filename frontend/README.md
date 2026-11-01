# CivicMesh citizen frontend

React + Vite + TypeScript frontend. This branch preserves the teammate's selected
framework; it currently differs from the original Next.js stack proposal.

```powershell
Set-Location frontend
npm.cmd ci
npm.cmd run api:generate
npm.cmd run typecheck
npm.cmd run build
npm.cmd test
npm.cmd run test:integration
```

For development use `npm.cmd run dev`. Configure public variables using .env.example.
No service-role keys belong in frontend variables. The map requires both
VITE_MAP_TILE_URL and VITE_MAP_ATTRIBUTION. No provider is contacted when these are absent.

Routes: /map, /incidents, /incidents/:id, /report, /reports/:id, /jobs/:id, /campaigns, /profile.
The shell includes auth controls, a location/photo/audio form, incident views and
follow-up/clarification forms. Empty and unavailable states contain no seeded citizen
records, campaigns, rewards, fabricated identities or invented government responses.
Old demo caches are ignored. Unconfigured mutations fail instead of reporting local success.

Uploads use /uploads/prepare and the returned private signed destination. Reports
use the OpenAPI DTO and an idempotency key; private history comes from /reports.
The browser polls /jobs/:id and submits exact checkpoint/interrupt replies to
/jobs/:id/answers. Results and human reviews display the stored backend data;
no browser call invokes AI. Follow-ups upload fresh owned evidence and open a
private assessment job. Sign-out/account changes clear private views and drafts.
Campaign/support/reward services are outside the implemented pilot.

The integration test starts the real API, database and worker locally with test-only
provider/Auth/Storage doubles. Install the backend environment first with
`uv sync --project backend --frozen --extra dev` from the repository root.
Production credentials are unnecessary for tests. A real deployment requires
owner-configured services and genuine staging verification; follow
[the deployment runbook](../docs/deployment-runbook.md).

The OpenAPI generator requires TypeScript 5.x; this project pins 5.9.3. Its minimatch
transitive dependency is overridden to the patched 11.0.1 release and validated by
type generation, compilation and npm audit. Generated API types are checked for
drift in CI.

Browser tests validate missing-service states, no runtime seed data, explicit coordinate
confirmation, missing-backend submission failures, and responsive layouts using isolated
test input only. They run headlessly; local Windows uses installed Edge and CI uses Chromium.
