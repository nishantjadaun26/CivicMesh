-- =============================================================================
-- CivicMesh Initial Database Schema & Security Foundation
-- PostgreSQL with PostGIS and pgvector
--
-- Coordinate storage convention:
-- WGS84 (SRID 4326). PostGIS geometries are constructed using ST_SetSRID(ST_MakePoint(longitude, latitude), 4326).
-- Note: longitude is the X-axis (first arg), latitude is the Y-axis (second arg).
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "postgis";
CREATE EXTENSION IF NOT EXISTS "vector";

-- -----------------------------------------------------------------------------
-- 1. Profiles (matches Supabase Auth users)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- -----------------------------------------------------------------------------
-- 2. Authorities & Official Sources
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.authorities (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    jurisdiction TEXT NOT NULL,
    contact_email TEXT,
    portal_url TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.source_documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    authority_id UUID NOT NULL REFERENCES public.authorities(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    sha256_hash TEXT NOT NULL,
    retrieved_at TIMESTAMPTZ NOT NULL,
    verified_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.source_chunks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES public.source_documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    embedding vector(768), -- Gemini text-embedding-004 explicit dimension
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(document_id, chunk_index)
);

-- -----------------------------------------------------------------------------
-- 3. Incidents (Approved Public View / Aggregated Issue)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.incidents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    category TEXT NOT NULL CHECK (category IN ('garbage', 'water_leak')),
    location GEOMETRY(Point, 4326) NOT NULL,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    observed_condition TEXT NOT NULL, -- Citizen observations or AI assessment
    authority_status TEXT NOT NULL DEFAULT 'unknown', -- Verified official authority updates only
    is_public BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_incidents_location ON public.incidents USING GIST(location);
CREATE INDEX IF NOT EXISTS idx_incidents_category_public ON public.incidents(category, is_public);

-- -----------------------------------------------------------------------------
-- 4. Reports (Citizen Private Submissions)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.reports (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    owner_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    category TEXT CHECK (category IN ('garbage', 'water_leak')),
    text TEXT NOT NULL DEFAULT '',
    location GEOMETRY(Point, 4326),
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    location_confirmed BOOLEAN NOT NULL DEFAULT FALSE,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'waiting_for_input', 'processed', 'failed')),
    extraction_result JSONB,
    idempotency_key TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (owner_id, idempotency_key)
);

CREATE INDEX IF NOT EXISTS idx_reports_owner ON public.reports(owner_id);
CREATE INDEX IF NOT EXISTS idx_reports_location ON public.reports USING GIST(location);
CREATE INDEX IF NOT EXISTS idx_reports_status ON public.reports(status);

-- -----------------------------------------------------------------------------
-- 5. Incident Reports (Reversible merge membership)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.incident_reports (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    incident_id UUID NOT NULL REFERENCES public.incidents(id) ON DELETE CASCADE,
    report_id UUID NOT NULL REFERENCES public.reports(id) ON DELETE CASCADE,
    similarity_score DOUBLE PRECISION,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (incident_id, report_id)
);

CREATE INDEX IF NOT EXISTS idx_incident_reports_incident ON public.incident_reports(incident_id);
CREATE INDEX IF NOT EXISTS idx_incident_reports_report ON public.incident_reports(report_id);

-- -----------------------------------------------------------------------------
-- 6. Evidence (Owner-bound media files)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.evidence (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    owner_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    report_id UUID REFERENCES public.reports(id) ON DELETE SET NULL,
    incident_id UUID REFERENCES public.incidents(id) ON DELETE SET NULL,
    storage_bucket TEXT NOT NULL,
    storage_path TEXT NOT NULL,
    mime_type TEXT NOT NULL,
    file_size_bytes BIGINT NOT NULL,
    sha256_hash TEXT,
    verified BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_evidence_owner ON public.evidence(owner_id);
CREATE INDEX IF NOT EXISTS idx_evidence_report ON public.evidence(report_id);

-- -----------------------------------------------------------------------------
-- 7. Jobs & Workflow Runs (Persistent Async Processing)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    owner_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    report_id UUID NOT NULL REFERENCES public.reports(id) ON DELETE CASCADE,
    kind TEXT NOT NULL DEFAULT 'report',
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'waiting_for_input', 'completed', 'failed')),
    attempts INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 3,
    error_code TEXT,
    error_message TEXT,
    checkpoint_id TEXT,
    pending_action JSONB,
    locked_at TIMESTAMPTZ,
    locked_by TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_jobs_owner ON public.jobs(owner_id);
CREATE INDEX IF NOT EXISTS idx_jobs_report ON public.jobs(report_id);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON public.jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_claimable ON public.jobs(status, attempts) WHERE status = 'pending';

CREATE TABLE IF NOT EXISTS public.workflow_runs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id UUID NOT NULL REFERENCES public.jobs(id) ON DELETE CASCADE,
    workflow_id UUID NOT NULL UNIQUE,
    owner_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    state TEXT NOT NULL,
    result_payload JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_workflow_runs_job ON public.workflow_runs(job_id);
CREATE INDEX IF NOT EXISTS idx_workflow_runs_workflow ON public.workflow_runs(workflow_id);

-- -----------------------------------------------------------------------------
-- 8. Status Events (Auditable Timeline: Observations vs Authority Updates)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.status_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    incident_id UUID REFERENCES public.incidents(id) ON DELETE CASCADE,
    report_id UUID REFERENCES public.reports(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL CHECK (event_type IN ('citizen_observation', 'ai_assessment', 'authority_update')),
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_status_events_incident ON public.status_events(incident_id);
CREATE INDEX IF NOT EXISTS idx_status_events_report ON public.status_events(report_id);

-- -----------------------------------------------------------------------------
-- 9. Row-Level Security (RLS) Policies
-- -----------------------------------------------------------------------------
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.authorities ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.source_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.source_chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.incidents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.incident_reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.evidence ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.workflow_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.status_events ENABLE ROW LEVEL SECURITY;

-- Profiles: Users can view and update their own profile
CREATE POLICY profiles_owner_select ON public.profiles FOR SELECT USING (id = auth.uid());
CREATE POLICY profiles_owner_update ON public.profiles FOR UPDATE USING (id = auth.uid());

-- Authorities & Sources: Publicly viewable by verified authorities catalog
CREATE POLICY authorities_select_all ON public.authorities FOR SELECT USING (true);
CREATE POLICY source_documents_select_all ON public.source_documents FOR SELECT USING (true);
CREATE POLICY source_chunks_select_all ON public.source_chunks FOR SELECT USING (true);

-- Incidents: Anyone can read approved public incidents
CREATE POLICY incidents_public_select ON public.incidents FOR SELECT USING (is_public = TRUE);

-- Reports: Private to the authenticated report owner (reads only; all writes mediated by backend API)
CREATE POLICY reports_owner_select ON public.reports FOR SELECT USING (owner_id = auth.uid());

-- Evidence: Private to the authenticated evidence owner (reads only; creation and binding mediated by backend API)
CREATE POLICY evidence_owner_select ON public.evidence FOR SELECT USING (owner_id = auth.uid());

-- Jobs: Private to the authenticated job owner
CREATE POLICY jobs_owner_select ON public.jobs FOR SELECT USING (owner_id = auth.uid());

-- Status Events: Public for approved public incidents, or owner-only for private reports
CREATE POLICY status_events_select ON public.status_events FOR SELECT USING (
    (report_id IS NOT NULL AND EXISTS (SELECT 1 FROM public.reports r WHERE r.id = report_id AND r.owner_id = auth.uid()))
);


-- Citizen evidence is private. Signed upload preparation is backend-only.
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES ('civicmesh-evidence', 'civicmesh-evidence', false, 20971520,
  ARRAY['image/jpeg','image/png','image/webp','audio/webm','audio/ogg','audio/mp4','audio/mpeg','audio/wav'])
ON CONFLICT (id) DO UPDATE SET public = false;
CREATE POLICY evidence_storage_owner_read ON storage.objects FOR SELECT TO authenticated
USING (bucket_id = 'civicmesh-evidence' AND EXISTS (
  SELECT 1 FROM public.evidence e WHERE e.storage_path = name
    AND e.owner_id = auth.uid() AND e.verified = true
));
