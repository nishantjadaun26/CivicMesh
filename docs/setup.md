# Windows PowerShell setup

Install Git, Node.js 24 LTS and uv (tested with 0.8.15). Use Python 3.11;
`uv sync --python 3.11` can provision it. The backend supports Python 3.11–3.13.
The repository root is already CivicMesh: there is no extra nested civicmesh directory.

```powershell
git clone https://github.com/nishantjadaun26/CivicMesh.git
Set-Location CivicMesh
Set-Location backend
Copy-Item .env.example .env
uv sync --frozen --python 3.11
uv run --frozen uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

In a second terminal, from the repository root:

```powershell
Set-Location frontend
Copy-Item .env.example .env.local
npm.cmd ci
npm.cmd run dev
```

Open http://localhost:3000 and http://localhost:8000/docs.
The app works without production secrets: it displays configuration/unavailable states.
Sign-in supports existing Supabase email/password users; provision genuine test accounts
through your project, not invented production users. Signup and signout UX are future work.

## Environment

| Variable | Scope | Meaning |
|---|---|---|
| NEXT_PUBLIC_API_BASE_URL | Frontend/public | Backend URL; default example localhost:8000 |
| NEXT_PUBLIC_SUPABASE_URL | Frontend/public | HTTPS Supabase project URL |
| NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY | Frontend/public | Publishable key only |
| NEXT_PUBLIC_MAP_TILE_URL | Frontend/public | Provider-approved Leaflet tile URL, including template placeholders |
| NEXT_PUBLIC_MAP_ATTRIBUTION | Frontend/public | Provider-required attribution; trusted deployment configuration, never citizen input |
| CORS_ORIGINS | Backend | JSON array of exact frontend origins; no wildcard/path |
| SUPABASE_URL | Backend | Trusted HTTPS project URL used for token verification |
| SUPABASE_PUBLISHABLE_KEY | Backend | Key for Supabase Auth user verification |
| SUPABASE_SERVICE_ROLE_KEY | Backend secret | Private Storage signing; never NEXT_PUBLIC_* |
| DATABASE_URL | Backend secret | SQLAlchemy `postgresql+psycopg://...` URL; use TLS for remote access |
| GEMINI_API_KEY | Worker secret | Paid model access; setup never invokes it |
| GEMINI_MODEL | Worker | Explicit project-approved model identifier; no guessed default |
| EMBEDDING_DIMENSIONS | Backend | 768; changing it requires coordinated schema/reindex work |

Keep local `.env` and `.env.local` untracked. Commented variables are optional until integration;
do not substitute empty strings for database URLs. Public frontend variables are compiled into
the client bundle. Restart/rebuild after changes. Choose the actual pilot locality and official
authority sources before enabling report persistence; there are no fabricated default coordinates.

## Verification and regeneration

From the repository root:

```powershell
Set-Location backend
uv run --frozen ruff check app tests ../scripts
uv run --frozen pytest
uv run --frozen python ../scripts/export_openapi.py
uv run --frozen python ../scripts/export_openapi.py --check
uv run --frozen python ../scripts/export_migration.py --check
Set-Location ../frontend
npm.cmd run generate:types
npm.cmd run lint
npm.cmd run typecheck
npm.cmd run build
Set-Location ..
New-Item -ItemType Directory -Force .cache | Out-Null
Invoke-WebRequest https://coderabbit.ai/integrations/schema.v2.json -OutFile .cache/coderabbit-schema.json
backend/.venv/Scripts/python.exe scripts/validate_coderabbit.py
```

Review and commit OpenAPI and generated TypeScript together. Never independently edit generated
types. `uv.lock` and `package-lock.json` pin the complete dependency sets. Use frozen/CI installs.

## Database validation

No local PostgreSQL/Docker was available during setup; no remote database was inspected or changed.
Install Docker Desktop and the Supabase CLI to test an isolated local project. Read the migration
and verify extension schemas before applying. In a disposable local Supabase project, copy the
migration into its migrations directory and run `supabase start` followed by `supabase migration up --local`.
Do not run a reset against an existing database. Check two authenticated users cannot read each
other's reports/evidence/jobs; anon cannot read private tables/media; only approved incident columns
are public; service writes enforce evidence ownership and valid authority provenance.

Before any remote migration: inspect existing tables, policies, extension versions/schemas,
storage buckets and migration history; take a backup; resolve naming conflicts; test on staging.
Then use the reviewed migration process for that project. Never run `create_all` against Supabase.
