# Data provenance and privacy

No seed complaints, fake acknowledgements, sample map markers, synthetic routing sources,
invented coordinates, fake model responses or claimed accuracy/savings/resolution metrics.
Contract examples and isolated test fixtures are development verification only. Tests never
load data into the product. An empty app or explicit unavailable error is an honest state.

Official sources retain authority, URL, retrieval timestamp, content SHA-256, supporting text,
media type and chunk/page references. Verification records belong to authorities. Retrieval is
not implemented: before adding it, use an official-domain allowlist, validate every redirect,
block private/loopback/link-local addresses after DNS resolution, bound download sizes/timeouts,
and prevent model-provided URLs or retrieved instructions from altering tool permissions.

Authority status defaults to unknown. A change requires an actual response/receipt reference
and received timestamp; AI or citizen observations cannot provide official authority status.
Observed conditions are appears_resolved, partly_resolved, persists, insufficient_evidence.
They require attribution and supporting evidence, not certainty inferred from missing information.
Database checks enforce basic separation; backend validation must verify provenance itself.

Profiles reference auth.users. Reports/evidence/jobs have owner read policies and no direct client
mutation grants. All 11 tables enable RLS. The backend connects using a secret, dedicated SQL role
provisioned for the API/worker; a trusted server role may bypass RLS, so repository methods MUST
filter by the verified owner. SQL credentials and Storage service-role keys stay server-side.
Use migration-owner credentials only for reviewed schema changes, not as a browser/API credential.
Provision the runtime SQL role with only required tables/operations; no schema ownership.

The public_incidents view is intentionally owner-executed with a restricted column projection,
an approval filter and no raw locations, reporters or media. Review/scrub public_summary before
approval. Clients cannot read the base incident table. No media is public in this foundation;
future redacted derivatives require a separate approval and access design.

Private Storage permits completed owner evidence reads. Signing uploads/downloads and cleanup
must enforce evidence ownership and expiry. Do not log signed URLs. Browser map loading is
optional and explains that tile requests disclose the viewed area to the provider.

Incident membership is append/unlink history: keep the original reports, stamp unlinked_at/by
with a reason when reversing a mistaken merge, then add a new membership. Never delete source
reports to merge incidents. There is a unique partial index for each report's active membership.
Before production, enforce audit-event immutability, retention/deletion rules and report consent.
