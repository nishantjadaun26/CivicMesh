# Deployment templates (not deployed)

No billable services or remote database changes were created. Do not activate the worker yet:
its entry point exits 78 until persistent leasing and checkpoint adapters are implemented/tested.

Vercel: import the GitHub repository, select `frontend` as Root Directory, Next.js framework,
Node 24, `npm ci`, `npm run build`. Configure the public frontend variables from setup.md.
Use the deployed API HTTPS URL and rebuild. Add the exact Vercel origin to backend CORS;
do not broadly enable arbitrary preview origins. Supabase Auth redirect/site settings should
match approved deployment origins when redirect-based auth is introduced.

Render: `render.yaml` describes the Docker web service and intended worker. Creating either
service may incur charges; this setup only commits configuration. Configure backend secrets in
Render, not YAML. The web Dockerfile installs the frozen lock on Python 3.11 and runs as non-root.
Health path `/health` is liveness only; the JSON readiness remains false until real dependencies
and adapters are verified. Do not use a 200 liveness response as proof of operational readiness.

The blueprint includes the future worker specification but does not disable its first deployment.
Create only the web service manually for a foundation preview, leaving the worker uncreated.
Do not apply the full blueprint until crash/retry/checkpoint tests pass; then verify worker health.

Supabase: inspect target tables/extensions/policies/storage/migration history first; back up;
validate on local/staging Supabase; apply reviewed migrations. Extension support and installed
schemas can vary. Initial DDL assumes extension types resolve on the migration search_path.
Do not rewrite an applied migration; add numbered forward migrations and update model checks.
Set private bucket policy and provision a least-privilege runtime SQL role. Never export a
service-role key to frontend configuration. See setup.md for local validation scenarios.
