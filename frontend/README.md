# CivicMesh citizen app

Frontend-only React + Vite + TypeScript application. Opens directly on Map; no landing page is implemented. All changes belong to `frontend/` on `feat/frontend`.

## Run

Requires Node 22.12+ (tested on Node 24) and npm.

```powershell
cd C:\forge\CivicMesh\frontend
npm install
npm run dev
```

Open the local URL printed by Vite. Production verification:

```powershell
npm run build
npm run preview -- --port 4173
```

In another terminal run `npm test`. Tests use installed Microsoft Edge in visible mode. Change `channel` in `playwright.config.ts` for a different installed browser. Tests intercept map tiles with fixtures to avoid repeatedly requesting public map infrastructure.

## Routes and architecture

- `/map`: default route, Leaflet markers, category/status/search filters, GPS, accessible list, issue preview and support/undo.
- `/report`: manual/GPS pin selection, photo validation/preview/removal, optional recording, category/campaign selection, review and submission.
- `/campaigns` and `/campaigns/:id`: local campaigns, linked reports, evidence with explicit consent, participation and sharing.
- `/profile`: seeded identity, derived report/campaign counts, chronological contributions and transparent demo rewards.

`src/app/App.tsx` owns navigation and routing. `components/map` contains map adapters. Feature modules own screen behavior. `lib/api/platform.ts` defines shared citizen data, typed report/campaign contracts and IndexedDB media storage. `lib/api/issues.ts` implements the issue service contract; replace these adapters when backend contracts are published. React external-store subscriptions keep campaign/profile consumers consistent; Map loads the same issue store on route entry.

## Demo boundaries

No API contracts exist in the repository. No backend, Supabase, authentication, government service or verification workflow is connected. The identity, reports, campaigns and award history are illustrative. Submissions and campaign membership persist only in this browser's local storage; uploaded photographs/audio live in IndexedDB. Do not use sensitive real-world data in this hackathon prototype.

Campaign evidence is opt-in per report. Seeded reports have no photographs; campaign covers use category artwork until consented evidence exists. Grouping is manually represented by the selected campaign, not AI. Reports start as Reported; verification status names are distinct labels only, not claims of a live verification service. New submissions earn no automatic points. Sharing invokes browser sharing or copies a URL; local reports are not accessible on other devices.

Map tiles require internet access and visible OpenStreetMap attribution. Set `VITE_MAP_TILE_URL` before building to replace the provider (update attribution for the chosen provider). Tests mock tiles. No marker clustering dependency is included for this small dataset; add clustering when real volumes justify it.

Real-phone keyboard, safe-area, recording and touch behavior still need hardware validation. Browser tests cover Edge desktop and emulated responsive viewports. Refreshing or leaving an unfinished report currently discards its draft; completed submissions persist.
