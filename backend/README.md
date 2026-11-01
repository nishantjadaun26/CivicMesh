# CivicMesh API and persistent worker

Run commands from the repository root. Python 3.11 and uv 0.8.15 are used in CI.

```powershell
uv sync --project backend --frozen --extra dev
backend/.venv/Scripts/ruff.exe check backend scripts
backend/.venv/Scripts/pytest.exe -q backend/tests backend/app/ai/tests
backend/.venv/Scripts/python.exe scripts/validate_migrations.py
backend/.venv/Scripts/python.exe scripts/export_openapi.py
```

On Linux use `.venv/bin/` instead of `.venv/Scripts/`. The backend lock includes
the local `civicmesh_ai` package, durable checkpointers and binary PostgreSQL driver.
Use uv's local-source resolution rather than attempting to fetch `civicmesh-ai`
from a package registry with a standalone pip install.

For development copy `backend/.env.example` to repository-root `.env` and set real
local/staging credentials privately. Review/apply database migrations and explicitly
provision PostgreSQL checkpoints using the owner instructions before running:

```powershell
backend/.venv/Scripts/uvicorn.exe backend.app.main:app --host 127.0.0.1 --port 8000 --no-access-log
backend/.venv/Scripts/python.exe -m backend.app.worker
```

Run API and worker in separate shells. Real worker jobs can invoke the configured
model. Tests use isolated providers only. No schema is automatically migrated at
startup; missing dependencies remain unavailable. Local SQLite checkpoints are
single-process development only; production requires PostgreSQL and session locks.

Health paths: `/health/live` process-only; `/health` diagnostic; `/health/ready`
requires database/schema access and a recent initialized worker. This does not
validate live model credentials or quota.

See [architecture/audit](../docs/integration-audit.md),
[all environment variables](../docs/environment.md),
[deployment/rollback/cleanup](../docs/deployment-runbook.md) and
[verification evidence](../docs/verification.md).
