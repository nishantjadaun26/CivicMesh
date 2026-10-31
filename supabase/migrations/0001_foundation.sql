-- Initial foundation: review against the target Supabase database before applying.
BEGIN;

CREATE EXTENSION IF NOT EXISTS postgis;

CREATE EXTENSION IF NOT EXISTS vector;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE authorities (
	name TEXT NOT NULL,
	jurisdiction TEXT NOT NULL,
	official_url TEXT NOT NULL,
	verified_at TIMESTAMP WITH TIME ZONE,
	verification_evidence TEXT,
	id UUID DEFAULT gen_random_uuid() NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id)
);

CREATE TABLE incidents (
	category VARCHAR(20) NOT NULL,
	location geography(POINT,4326) NOT NULL,
	public_summary TEXT,
	public_approved_at TIMESTAMP WITH TIME ZONE,
	authority_status VARCHAR(30) DEFAULT 'unknown' NOT NULL,
	authority_response_reference TEXT,
	authority_response_received_at TIMESTAMP WITH TIME ZONE,
	observed_condition VARCHAR(30),
	observation_attribution TEXT,
	observation_evidence_reference TEXT,
	id UUID DEFAULT gen_random_uuid() NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	CHECK (category IN ('garbage','water_leak')),
	CHECK (authority_status IN ('unknown','acknowledged','in_progress','resolved')),
	CHECK (authority_status = 'unknown' OR (authority_response_reference IS NOT NULL AND authority_response_received_at IS NOT NULL)),
	CHECK (observed_condition IS NULL OR observed_condition IN ('appears_resolved','partly_resolved','persists','insufficient_evidence')),
	CHECK (observed_condition IS NULL OR (observation_attribution IS NOT NULL AND observation_evidence_reference IS NOT NULL)),
	CHECK (public_approved_at IS NULL OR public_summary IS NOT NULL)
);

CREATE INDEX idx_incidents_location ON incidents USING gist (location);

CREATE INDEX ix_incidents_public_page ON incidents (created_at, id) WHERE public_approved_at IS NOT NULL;

CREATE TABLE profiles (
	id UUID NOT NULL,
	display_name VARCHAR(100),
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(id) REFERENCES auth.users (id)
);

CREATE TABLE source_documents (
	authority_id UUID NOT NULL,
	url TEXT NOT NULL,
	retrieved_at TIMESTAMP WITH TIME ZONE NOT NULL,
	content_sha256 VARCHAR(64) NOT NULL,
	supporting_text TEXT NOT NULL,
	media_type VARCHAR(100) NOT NULL,
	id UUID DEFAULT gen_random_uuid() NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (url, content_sha256),
	FOREIGN KEY(authority_id) REFERENCES authorities (id)
);

CREATE INDEX ix_source_documents_authority_id ON source_documents (authority_id);

CREATE TABLE reports (
	owner_id UUID NOT NULL,
	category VARCHAR(20) NOT NULL,
	text TEXT NOT NULL,
	location geography(POINT,4326) NOT NULL,
	location_confirmed BOOLEAN NOT NULL,
	extraction JSONB,
	idempotency_key VARCHAR(128) NOT NULL,
	id UUID DEFAULT gen_random_uuid() NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (owner_id, idempotency_key),
	CHECK (category IN ('garbage','water_leak')),
	CHECK (location_confirmed = true),
	FOREIGN KEY(owner_id) REFERENCES profiles (id)
);

CREATE INDEX idx_reports_location ON reports USING gist (location);

CREATE INDEX ix_reports_owner_id ON reports (owner_id);

CREATE TABLE source_chunks (
	document_id UUID NOT NULL,
	ordinal INTEGER NOT NULL,
	text TEXT NOT NULL,
	page_number INTEGER,
	embedding VECTOR(768),
	embedding_model TEXT,
	id UUID DEFAULT gen_random_uuid() NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (document_id, ordinal),
	CHECK ((embedding IS NULL) = (embedding_model IS NULL)),
	FOREIGN KEY(document_id) REFERENCES source_documents (id)
);

CREATE INDEX ix_chunks_embedding ON source_chunks USING hnsw (embedding vector_cosine_ops);

CREATE INDEX ix_source_chunks_document_id ON source_chunks (document_id);

CREATE TABLE evidence (
	owner_id UUID NOT NULL,
	report_id UUID,
	incident_id UUID,
	object_path TEXT NOT NULL,
	mime_type VARCHAR(100) NOT NULL,
	size_bytes INTEGER NOT NULL,
	uploaded_at TIMESTAMP WITH TIME ZONE,
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
	sha256 VARCHAR(64),
	id UUID DEFAULT gen_random_uuid() NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	CHECK (mime_type IN ('image/jpeg','image/png','image/webp','audio/webm','audio/ogg','audio/mp4','audio/mpeg','audio/wav')),
	CHECK (size_bytes > 0 AND size_bytes <= CASE WHEN mime_type LIKE 'image/%%' THEN 10485760 ELSE 20971520 END),
	CHECK (report_id IS NULL OR incident_id IS NULL),
	FOREIGN KEY(owner_id) REFERENCES profiles (id),
	FOREIGN KEY(report_id) REFERENCES reports (id),
	FOREIGN KEY(incident_id) REFERENCES incidents (id),
	UNIQUE (object_path)
);

CREATE INDEX ix_evidence_incident_id ON evidence (incident_id);

CREATE INDEX ix_evidence_owner_id ON evidence (owner_id);

CREATE INDEX ix_evidence_report_id ON evidence (report_id);

CREATE TABLE incident_reports (
	incident_id UUID NOT NULL,
	report_id UUID NOT NULL,
	linked_by UUID NOT NULL,
	unlinked_at TIMESTAMP WITH TIME ZONE,
	unlinked_by UUID,
	reason TEXT NOT NULL,
	id UUID DEFAULT gen_random_uuid() NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	CHECK ((unlinked_at IS NULL) = (unlinked_by IS NULL)),
	FOREIGN KEY(incident_id) REFERENCES incidents (id),
	FOREIGN KEY(report_id) REFERENCES reports (id),
	FOREIGN KEY(linked_by) REFERENCES profiles (id),
	FOREIGN KEY(unlinked_by) REFERENCES profiles (id)
);

CREATE INDEX ix_incident_reports_incident_id ON incident_reports (incident_id);

CREATE INDEX ix_incident_reports_linked_by ON incident_reports (linked_by);

CREATE INDEX ix_incident_reports_report_id ON incident_reports (report_id);

CREATE INDEX ix_incident_reports_unlinked_by ON incident_reports (unlinked_by);

CREATE UNIQUE INDEX uq_report_active_membership ON incident_reports (report_id) WHERE unlinked_at IS NULL;

CREATE TABLE jobs (
	owner_id UUID NOT NULL,
	report_id UUID,
	incident_id UUID,
	kind VARCHAR(60) NOT NULL,
	status VARCHAR(30) DEFAULT 'queued' NOT NULL,
	attempts INTEGER DEFAULT '0' NOT NULL,
	max_attempts INTEGER DEFAULT '3' NOT NULL,
	available_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	started_at TIMESTAMP WITH TIME ZONE,
	finished_at TIMESTAMP WITH TIME ZONE,
	lease_token UUID,
	lease_expires_at TIMESTAMP WITH TIME ZONE,
	error_code VARCHAR(100),
	error_message TEXT,
	idempotency_key VARCHAR(128) NOT NULL,
	id UUID DEFAULT gen_random_uuid() NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (owner_id, kind, idempotency_key),
	CHECK (status IN ('queued','running','waiting_for_input','succeeded','failed','cancelled')),
	CHECK (attempts >= 0 AND max_attempts BETWEEN 1 AND 10 AND attempts <= max_attempts),
	CHECK (status <> 'running' OR (lease_token IS NOT NULL AND lease_expires_at IS NOT NULL)),
	FOREIGN KEY(owner_id) REFERENCES profiles (id),
	FOREIGN KEY(report_id) REFERENCES reports (id),
	FOREIGN KEY(incident_id) REFERENCES incidents (id)
);

CREATE INDEX ix_jobs_claim ON jobs (status, available_at);

CREATE INDEX ix_jobs_incident_id ON jobs (incident_id);

CREATE INDEX ix_jobs_owner_id ON jobs (owner_id);

CREATE INDEX ix_jobs_report_id ON jobs (report_id);

CREATE TABLE status_events (
	incident_id UUID NOT NULL,
	actor_id UUID,
	kind VARCHAR(30) NOT NULL,
	authority_status VARCHAR(30),
	observed_condition VARCHAR(30),
	authority_response_reference TEXT,
	authority_response_received_at TIMESTAMP WITH TIME ZONE,
	evidence_id UUID,
	attribution TEXT NOT NULL,
	occurred_at TIMESTAMP WITH TIME ZONE NOT NULL,
	id UUID DEFAULT gen_random_uuid() NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	CHECK (kind IN ('authority_update','citizen_observation','ai_assessment')),
	CHECK ((kind = 'authority_update' AND authority_status IS NOT NULL AND authority_status IN ('acknowledged','in_progress','resolved') AND authority_response_reference IS NOT NULL AND authority_response_received_at IS NOT NULL AND observed_condition IS NULL) OR (kind IN ('citizen_observation','ai_assessment') AND authority_status IS NULL AND observed_condition IS NOT NULL AND evidence_id IS NOT NULL)),
	CHECK (observed_condition IS NULL OR observed_condition IN ('appears_resolved','partly_resolved','persists','insufficient_evidence')),
	FOREIGN KEY(incident_id) REFERENCES incidents (id),
	FOREIGN KEY(actor_id) REFERENCES profiles (id),
	FOREIGN KEY(evidence_id) REFERENCES evidence (id)
);

CREATE INDEX ix_status_events_actor_id ON status_events (actor_id);

CREATE INDEX ix_status_events_evidence_id ON status_events (evidence_id);

CREATE INDEX ix_status_events_incident_id ON status_events (incident_id);

CREATE TABLE workflow_runs (
	job_id UUID NOT NULL,
	thread_id VARCHAR(100) NOT NULL,
	checkpoint_reference TEXT,
	graph_version VARCHAR(50) NOT NULL,
	status VARCHAR(30) DEFAULT 'queued' NOT NULL,
	id UUID DEFAULT gen_random_uuid() NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (job_id),
	FOREIGN KEY(job_id) REFERENCES jobs (id),
	UNIQUE (thread_id)
);

-- Included by scripts/export_migration.py. No direct client mutations in foundation.
DO $$
DECLARE tbl text;
BEGIN
  FOREACH tbl IN ARRAY ARRAY['profiles','reports','incidents','incident_reports','evidence',
    'authorities','source_documents','source_chunks','jobs','workflow_runs','status_events'] LOOP
    EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', tbl);
    EXECUTE format('REVOKE ALL ON public.%I FROM anon, authenticated', tbl);
    EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON public.%I TO service_role', tbl);
  END LOOP;
END $$;

GRANT SELECT ON profiles, reports, evidence, jobs TO authenticated;
CREATE POLICY profiles_owner_read ON profiles FOR SELECT TO authenticated USING (id = (SELECT auth.uid()));
CREATE POLICY reports_owner_read ON reports FOR SELECT TO authenticated USING (owner_id = (SELECT auth.uid()));
CREATE POLICY evidence_owner_read ON evidence FOR SELECT TO authenticated USING (owner_id = (SELECT auth.uid()));
CREATE POLICY jobs_owner_read ON jobs FOR SELECT TO authenticated USING (owner_id = (SELECT auth.uid()));

-- Safe column projection: base incident records remain inaccessible to clients.
-- This intentionally owner-executed view exposes only approved, scrubbed fields.
CREATE VIEW public.public_incidents WITH (security_barrier = true) AS
SELECT id AS incident_id, category, public_summary, authority_status, observed_condition, created_at
FROM public.incidents WHERE public_approved_at IS NOT NULL;
REVOKE ALL ON public.public_incidents FROM PUBLIC;
GRANT SELECT ON public.public_incidents TO anon, authenticated, service_role;

CREATE FUNCTION public.touch_updated_at() RETURNS trigger LANGUAGE plpgsql
SET search_path = pg_catalog AS $$
BEGIN NEW.updated_at = now(); RETURN NEW; END $$;
DO $$
DECLARE tbl text;
BEGIN
  FOREACH tbl IN ARRAY ARRAY['profiles','reports','incidents','incident_reports','evidence',
    'authorities','source_documents','source_chunks','jobs','workflow_runs','status_events'] LOOP
    EXECUTE format('CREATE TRIGGER touch_updated_at BEFORE UPDATE ON public.%I FOR EACH ROW EXECUTE FUNCTION public.touch_updated_at()', tbl);
  END LOOP;
END $$;

-- Reject cross-owner evidence binding even for backend writes.
CREATE FUNCTION public.check_evidence_owner() RETURNS trigger LANGUAGE plpgsql
SET search_path = pg_catalog, public AS $$
BEGIN
  IF NEW.report_id IS NOT NULL AND NOT EXISTS (
    SELECT 1 FROM public.reports WHERE id = NEW.report_id AND owner_id = NEW.owner_id
  ) THEN RAISE EXCEPTION 'Evidence/report ownership mismatch'; END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER evidence_owner BEFORE INSERT OR UPDATE ON public.evidence
FOR EACH ROW EXECUTE FUNCTION public.check_evidence_owner();

-- Signed uploads are issued only by backend after a pending evidence row exists.
-- No broad client write/delete/list policies. Reads also require matching ownership.
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES ('citizen-evidence', 'citizen-evidence', false, 20971520,
  ARRAY['image/jpeg','image/png','image/webp','audio/webm','audio/ogg','audio/mp4','audio/mpeg','audio/wav']);
CREATE POLICY citizen_evidence_read ON storage.objects FOR SELECT TO authenticated
USING (bucket_id = 'citizen-evidence' AND EXISTS (
  SELECT 1 FROM public.evidence e WHERE e.object_path = name
    AND e.owner_id = (SELECT auth.uid()) AND e.uploaded_at IS NOT NULL
));


COMMIT;
