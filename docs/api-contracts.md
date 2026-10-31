# Shared API contract

Source: `backend/app/schemas/contracts.py` and routes. Generated: `contracts/openapi.json`.
Frontend: `frontend/src/types/api.generated.ts`, regenerated with `npm run generate:types`.

All identifiers are UUID strings. Timestamps are RFC3339 with timezone offsets (store UTC).
Unknown optional values serialize as null; missing model information must never be invented.
Common errors: `{code, message, request_id, details}`; details contain sanitized field/type
information, not submitted values. `X-Request-ID` matches the body. Never expose raw provider
errors, database URLs, signed URLs, tokens or private content in errors/logs.

| Method/path | Authentication | Intended result |
|---|---|---|
| GET /health | None | 200 liveness and service readiness separately |
| POST /uploads/prepare | Bearer | UploadPrepared; owner-bound pending evidence |
| POST /reports | Bearer + Idempotency-Key | 202 report_id and job_id |
| GET /reports/{report_id} | Bearer, owner only | Report including nullable extraction |
| POST /reports/{report_id}/answers | Bearer, owner + Idempotency-Key | 202 job_id |
| GET /jobs/{job_id} | Bearer, owner only | Job state, attempts, timestamps, sanitized error |
| GET /incidents | None | Approved incident page only |
| GET /incidents/{incident_id} | None | Approved incident DTO only |
| POST /incidents/{incident_id}/follow-ups | Bearer + Idempotency-Key | 202 job_id |

These are contracts: only health currently produces a successful operational response.
Private routes reject missing tokens with 401. Configured auth verifies tokens through Supabase
Auth `/auth/v1/user`; it never trusts an arbitrary UUID or unsigned JWT. Missing configuration
returns 503. Configured-but-unimplemented operations return 501. Invalid input returns 422.
Future owner mismatch should return 404 to avoid existence leaks. Add 409 for reused idempotency
keys with conflicting content when persistence is implemented, and regenerate the contract.

Pagination: limit defaults to 20, maximum 100. Opaque cursor (at most 256 characters), stable
keyset order `(created_at DESC, id DESC)`. `next_cursor: null` means no next page. No offsets,
private report counts, or implied completeness. The public DTO contains no precise coordinates,
owners or unapproved media. The frontend renders an empty state only after a real successful
empty response; service failures are never translated into an empty array.

Jobs: queued -> running -> succeeded/failed/waiting_for_input; waiting_for_input resumes through
an authorized request; cancelled is terminal. A retry returns to queued with an available_at
deadline. A job must not report succeeded before persistence/checkpoints commit. Output retrieval
is owner-authorized via reports. Workflow thread IDs are not authentication.

## Private uploads

Prepare accepts MIME and declared size, not an owner ID or object path. Images: JPEG/PNG/WebP,
1–10 MiB (byte minimum is 1). Audio: WebM/Ogg/MP4/MPEG/WAV, 1 byte–20 MiB. At most 10 evidence
IDs per report. No SVG, arbitrary documents or remote-URL uploads.

The future implementation must create a pending evidence row owned by the verified subject;
generate an unpredictable object path `owner_id/evidence_id`; issue a short-lived private upload
URL with the specified HTTP method and required headers; and return evidence_id plus expires_at.
Treat that signed URL as a bearer secret. The client must obey the returned method/headers.
Declared MIME/size are not trusted: inspect actual storage metadata and content signatures before
binding; reject missing, expired, oversize, foreign-owned or already-bound objects. Strip EXIF
before any approved public derivative. The bucket ceiling is 20 MiB; the backend must additionally
enforce the tighter image limit. No endpoint signs anything until this implementation exists.

POST /reports binds only the current user's completed uploads in the same transaction as report
and job creation. The DB also rejects cross-owner report/evidence bindings. Pending upload cleanup
and safe signed-download issuance remain future work. No raw media is published by default.

Idempotency-Key is 8–128 characters, scoped by owner and operation. Persistence must compare a
canonical payload hash before replaying an existing response; the foundation only defines the
header and unique keys, not complete replay behavior. Before enabling submission, make the UI
retain keys and completed upload IDs across ambiguous network failures. Never retry a consequential
operation with a fresh identity until its previous outcome is known.
