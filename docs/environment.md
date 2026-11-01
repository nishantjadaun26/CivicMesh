# Environment inventory

This inventory follows `Settings` in `backend/app/core/config.py`, direct Vite
reads, the standalone AI CLI, and `Dockerfile`. No receipt, SMTP, embedding-model,
Redis or frontend AI key is required. `STORAGE_DOCUMENTS_BUCKET` was removed because
no runtime implementation used it.

All frontend variables below are public **build-time** values. Set them in Vercel
Project Settings → Environment Variables, selecting Preview or Production, or in
`frontend/.env.local` locally. Rebuild/redeploy after every change. Frontend values
must describe the same Supabase project and API environment.

| Variable | Purpose and required status | Classification | Obtain/set value |
|---|---|---|---|
| `VITE_API_URL` | Required to use API features; absolute API origin without `/api` | Public | Owner's deployed HTTPS API URL, e.g. `https://api.example.org`; local `http://127.0.0.1:8000` |
| `VITE_SUPABASE_URL` | Required for sign-in and private upload origin checks | Public | Supabase project URL |
| `VITE_SUPABASE_ANON_KEY` | Required for browser Auth; publishable key or legacy anon key | Public | Supabase project API keys; never service_role or sb_secret_ |
| `VITE_MAP_TILE_URL` | Optional tile template; map unavailable when absent | Public, including any browser token | Owner-approved map provider template using `{z}`, `{x}`, `{y}`; restrict browser tokens by origin |
| `VITE_MAP_ATTRIBUTION` | Required when using map tiles | Public | Provider-required attribution; owner-controlled HTML passed to Leaflet |

Server variables are **runtime** values. Set them in the API/worker host's secret
or environment settings, or repository-root ignored `.env` locally. Restart or
redeploy every affected process after changes. Do not put a server `.env` in Vercel
or the Docker build context. Model variables are loaded by the worker through
Settings; the optional standalone AI CLI reads `GEMINI_API_KEY` and `GEMINI_MODEL`
directly from its process environment.

| Variable | Component | Purpose / required status and default | Classification | Obtain/set value |
|---|---|---|---|---|
| `ENVIRONMENT` | API + worker | Set `production` for staging/production validation; default development | Public | Host environment setting; use `test` only in isolated tests |
| `LOG_LEVEL` | API | Optional INFO default; SQL debug logging enabled only in development | Public | Operator logging choice |
| `REQUEST_TIMEOUT_SECONDS` | API | Optional 30; bounds JSON requests, 1–120 | Public | Operator; normal report processing happens in worker |
| `WRITE_REQUESTS_PER_HOUR` | API | Optional 60 authenticated mutations per owner per fixed UTC hour, shared across replicas | Public | Operator quota; do not disable abuse controls |
| `CORS_ORIGINS` | API + worker settings validation | Required explicit HTTPS origins in production; comma-separated or JSON list; default local port 5173 | Public | Actual frontend origins, including separately approved previews; no wildcard/path/trailing slash |
| `DATABASE_URL` | API + worker | Required PostgreSQL SQLAlchemy URL in production, `postgresql+asyncpg://…?ssl=require` | Secret | Supabase Connect dialog; URL-encode password. Production code also verifies TLS certificates/hostname using system trust |
| `DATABASE_SSL_ROOT_CERT` | API + worker / checkpoint provisioning | Required when the database CA is absent from system trust; optional otherwise | Public certificate-file path | Download the correct project's CA from Supabase Database Settings → SSL Configuration, mount on both hosts, set its path; also used by psycopg verify-full |
| `SUPABASE_URL` | API + worker | Required real HTTPS project URL | Public | Supabase project dashboard; same project as browser |
| `SUPABASE_JWT_SECRET` | API | Optional; required only for legacy HS256 user JWTs; blank for ES256/RS256 JWKS | Secret | Legacy project JWT secret; never browser anon key; rotating it affects existing HS256 sessions |
| `SUPABASE_SERVICE_ROLE_KEY` | API + worker | Required server-side legacy service_role JWT for private Storage signing/download | Secret, privileged | Supabase API keys → legacy service_role; store only on server |
| `STORAGE_EVIDENCE_BUCKET` | API + worker | Optional default `civicmesh-evidence`; keep this value with supplied policies | Public | Bucket created by migration; changing it also requires reviewed bucket/policy changes |
| `PILOT_LOCALITY_NAME` | API + worker | Required nonempty in production; exact authority-catalog jurisdiction | Public | Owner verifies actual pilot jurisdiction; no sample locality is shipped |
| `PILOT_LATITUDE` | API + worker | Required production center latitude | Public | Owner-confirmed real center, WGS84 |
| `PILOT_LONGITUDE` | API + worker | Required production center longitude | Public | Owner-confirmed real center, WGS84 |
| `PILOT_RADIUS_METERS` | Worker | Optional 5000; authority routing withheld outside configured radius | Public | Owner-approved pilot boundary |
| `GEMINI_API_KEY` | Worker / standalone AI CLI | Required for real model processing, never needed by browser | Secret | Owner's Google AI Studio project; inspect quota/billing before any genuine verification |
| `GEMINI_MODEL` | Worker / standalone AI CLI | Required explicit model; no guessed default | Public identifier | Exact available model ID supporting images/audio and structured JSON in owner's project |
| `WORKER_POLL_INTERVAL_SECONDS` | Worker | Optional 2; idle poll interval, 0.1–60 | Public | Operator |
| `WORKER_MAX_RETRIES` | API + worker | Optional 3; persisted failure budget on newly created jobs, 1–5 | Public | Operator. Existing job budgets are preserved; valid human replies do not reset failure counts |
| `WORKER_JOB_TIMEOUT_SECONDS` | Worker | Optional 300; one execution slice timeout, 30–600 | Public | Operator; less than lease |
| `WORKER_LEASE_SECONDS` | Worker | Optional 600; stale running-job recovery threshold, 60–1200 | Public | Must exceed execution timeout; do not use as a reason to run simultaneous work on one job |
| `CHECKPOINT_DATABASE_URL` | Worker + owner provisioning command | Required in production; psycopg `postgresql://…?sslmode=verify-full` DSN | Secret | Same logical database; direct or **session** connection; private `civicmesh_checkpoints` search_path is forced in code |
| `LOCAL_CHECKPOINT_PATH` | Development worker | Optional `.cache/checkpoints.sqlite`; used only when checkpoint DSN is empty, forbidden production fallback | Secret-bearing file path | Owner-controlled private local directory; includes report state |
| `PORT` | Container API | Optional 8000 default; host may provide another port | Public | Docker start command / host-provided port |

The worker's application `DATABASE_URL` must also use a direct or **session**
connection: a PostgreSQL session advisory lock spans multiple transactions. A
transaction pooler can move that session and invalidate exclusion. Use session
connections for both components to simplify deployment. Supabase's connection
guide explains connection modes and network compatibility. [Official connection guide](https://supabase.com/docs/guides/database/connecting-to-postgres)

The container supplies `PATH`, `PYTHONUNBUFFERED=1` and `UV_LINK_MODE=copy` itself.
They are tooling settings, with no owner-provided secrets. `CI`, `PYTHONPATH`,
`UV_PYTHON` and `UV_CACHE_DIR` are test/build tooling controls. The only dedicated
database-test input is `CIVICMESH_TEST_POSTGRES_URL`; tests refuse non-loopback
hosts or a database name other than `civicmesh_test`. Never point it at a live
project. Browser harness credentials are isolated fixtures under test directories,
excluded from the production image.

Vercel changes affect new deployments, and Vite prefixes expose values to the
browser. Build validation rejects obvious server-key variable names and service-role
keys in the public key field; that guard supplements careful dashboard configuration.
[Vercel environment variables](https://vercel.com/docs/environment-variables),
[Vite environment variables](https://vite.dev/guide/env-and-mode)
