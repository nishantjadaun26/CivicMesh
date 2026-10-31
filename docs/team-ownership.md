# Team ownership

| Teammate | Branch | Owned paths and work |
|---|---|---|
| 1 | feat/frontend | frontend/: reporting, map, recording, clarification forms, incident timeline, follow-up UI |
| 2 | feat/ai-workflow | backend/app/ai/: Gemini, LangGraph, extraction, clarification, complaints, follow-up assessment |
| 3 | feat/backend | backend/app/api, database, services, worker, supabase/: authentication, persistence, matching, routing retrieval, jobs, deployment |

Coordinate changes to `backend/app/schemas`, contracts, dependency files/locks, migrations,
root deployment and CI. AI extraction schema edits need teammate 3 review; API changes need
teammate 1 review and regenerated types. Do not directly access the database from AI nodes.
Backend tools own identity, filtering, retrieval and provenance. Frontend never receives a
service-role key. No CODEOWNERS file invents unknown GitHub usernames.

First integration milestone: **real report submission -> persistence -> real AI extraction ->
frontend result**. Teammate 3 first implements atomic text-report + job persistence and owner reads;
teammate 2 connects extraction through a durable worker/checkpointer; teammate 1 displays job
status and the real extraction. Use a genuine consenting citizen observation. Keep media signing,
matching and authority routing disabled until individually verified. Record a real failure as a
failure; never substitute a sample result. One small cross-module PR should validate this path.
