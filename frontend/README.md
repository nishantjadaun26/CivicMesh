# CivicMesh citizen frontend

React + Vite + TypeScript frontend. This branch preserves the teammate's selected
framework; it currently differs from the original Next.js stack proposal.

```powershell
Set-Location frontend
npm.cmd ci
npm.cmd run typecheck
npm.cmd run build
npm.cmd test
```

For development use `npm.cmd run dev`. Configure public variables using .env.example.
No service-role keys belong in frontend variables. The map requires both
VITE_MAP_TILE_URL and VITE_MAP_ATTRIBUTION. No provider is contacted when these are absent.

Routes: /map, /incidents, /incidents/:id, /report, /campaigns, /profile.
The shell includes auth controls, a location/photo/audio form, incident views and
follow-up/clarification forms. Empty and unavailable states contain no seeded citizen
records, campaigns, rewards, fabricated identities or invented government responses.
Old demo caches are ignored. Unconfigured mutations fail instead of reporting local success.

Whole-project integration is still required: adapt the service DTOs and upload/report/
clarification paths to contracts/openapi.json, generate shared API types, connect real job
polling, and implement campaign/support services if retained. The frontend currently
rejects incompatible incident response shapes explicitly. It must not be described as
end-to-end operational before those contracts are connected and tested.

Browser tests validate missing-service states, no runtime seed data, explicit coordinate
confirmation, missing-backend submission failures, and responsive layouts using isolated
test input only. They run headlessly; local Windows uses installed Edge and CI uses Chromium.
