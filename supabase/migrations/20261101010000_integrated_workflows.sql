-- Integration expansion. Apply in staging first through tracked Supabase migrations.
-- No existing report, evidence or incident rows are deleted.

INSERT INTO public.profiles (id)
SELECT owner_id FROM public.reports UNION SELECT owner_id FROM public.evidence
UNION SELECT owner_id FROM public.jobs UNION SELECT owner_id FROM public.workflow_runs
ON CONFLICT (id) DO NOTHING;

ALTER TABLE public.reports DROP CONSTRAINT reports_owner_id_fkey;
ALTER TABLE public.reports ADD CONSTRAINT reports_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES public.profiles(id) ON DELETE CASCADE;
ALTER TABLE public.evidence DROP CONSTRAINT evidence_owner_id_fkey;
ALTER TABLE public.evidence ADD CONSTRAINT evidence_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES public.profiles(id) ON DELETE CASCADE;
ALTER TABLE public.jobs DROP CONSTRAINT jobs_owner_id_fkey;
ALTER TABLE public.jobs ADD CONSTRAINT jobs_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES public.profiles(id) ON DELETE CASCADE;
ALTER TABLE public.workflow_runs DROP CONSTRAINT workflow_runs_owner_id_fkey;
ALTER TABLE public.workflow_runs ADD CONSTRAINT workflow_runs_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES public.profiles(id) ON DELETE CASCADE;

CREATE TABLE public.follow_ups (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  owner_id uuid NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  incident_id uuid NOT NULL REFERENCES public.incidents(id) ON DELETE CASCADE,
  text text NOT NULL DEFAULT '', same_location_confirmed boolean NOT NULL CHECK (same_location_confirmed),
  idempotency_key text, status text NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending','processing','waiting_for_input','processed','failed')),
  result jsonb, created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT uq_follow_up_owner_key UNIQUE(owner_id, idempotency_key)
);
CREATE INDEX idx_follow_ups_incident ON public.follow_ups(incident_id);
ALTER TABLE public.follow_ups ENABLE ROW LEVEL SECURITY;
CREATE POLICY follow_ups_owner_select ON public.follow_ups FOR SELECT TO authenticated USING (owner_id = auth.uid());

ALTER TABLE public.evidence ADD COLUMN follow_up_id uuid REFERENCES public.follow_ups(id) ON DELETE SET NULL;
CREATE INDEX idx_evidence_follow_up ON public.evidence(follow_up_id);
ALTER TABLE public.jobs ALTER COLUMN report_id DROP NOT NULL;
ALTER TABLE public.jobs ADD COLUMN follow_up_id uuid UNIQUE REFERENCES public.follow_ups(id) ON DELETE CASCADE;
ALTER TABLE public.jobs ADD COLUMN available_at timestamptz NOT NULL DEFAULT now();
ALTER TABLE public.jobs ADD COLUMN failures integer NOT NULL DEFAULT 0 CHECK (failures >= 0);
ALTER TABLE public.jobs ADD CONSTRAINT jobs_subject CHECK (
  (kind = 'report' AND report_id IS NOT NULL AND follow_up_id IS NULL)
  OR (kind = 'follow_up' AND report_id IS NULL AND follow_up_id IS NOT NULL)
);
-- Abort for operator investigation if legacy duplicates exist; never silently discard jobs.
ALTER TABLE public.jobs ADD CONSTRAINT uq_jobs_report UNIQUE(report_id);
CREATE INDEX idx_jobs_available ON public.jobs(status, available_at);
ALTER TABLE public.workflow_runs ADD CONSTRAINT uq_workflow_runs_job UNIQUE(job_id);

CREATE TABLE public.worker_heartbeats (worker_id varchar(100) PRIMARY KEY, last_seen timestamptz NOT NULL DEFAULT now());
CREATE TABLE public.rate_windows (
  owner_id uuid NOT NULL, window_start timestamptz NOT NULL, count integer NOT NULL DEFAULT 0,
  PRIMARY KEY(owner_id, window_start)
);
ALTER TABLE public.worker_heartbeats ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.rate_windows ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.worker_heartbeats, public.rate_windows FROM anon, authenticated;

ALTER TABLE public.reports ADD CONSTRAINT report_coordinates CHECK (
  (latitude IS NULL AND longitude IS NULL AND NOT location_confirmed)
  OR (latitude IS NOT NULL AND longitude IS NOT NULL AND latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180)
);
ALTER TABLE public.incidents ADD CONSTRAINT incident_coordinates CHECK (latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180);

CREATE FUNCTION public.sync_civicmesh_location() RETURNS trigger LANGUAGE plpgsql SET search_path = public, extensions AS $$
BEGIN
  NEW.location := CASE WHEN NEW.latitude IS NOT NULL AND NEW.longitude IS NOT NULL
    THEN ST_SetSRID(ST_MakePoint(NEW.longitude, NEW.latitude),4326) ELSE NULL END;
  RETURN NEW;
END $$;
CREATE TRIGGER reports_location BEFORE INSERT OR UPDATE OF latitude, longitude ON public.reports FOR EACH ROW EXECUTE FUNCTION public.sync_civicmesh_location();
CREATE TRIGGER incidents_location BEFORE INSERT OR UPDATE OF latitude, longitude ON public.incidents FOR EACH ROW EXECUTE FUNCTION public.sync_civicmesh_location();

-- Only backend database credentials may write workflow state. Private checkpoint
-- tables are provisioned separately by the explicit init_checkpoints command.
CREATE SCHEMA IF NOT EXISTS civicmesh_checkpoints;
REVOKE ALL ON SCHEMA civicmesh_checkpoints FROM PUBLIC, anon, authenticated, service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA civicmesh_checkpoints REVOKE ALL ON TABLES FROM PUBLIC, anon, authenticated, service_role;

UPDATE storage.buckets SET public=false, file_size_limit=10485760,
  allowed_mime_types=ARRAY['image/jpeg','image/png','image/webp','audio/webm','audio/ogg','audio/mp4','audio/mpeg','audio/wav']
WHERE id='civicmesh-evidence';
DROP POLICY evidence_storage_owner_read ON storage.objects;
CREATE POLICY evidence_storage_owner_read ON storage.objects FOR SELECT TO authenticated
USING (bucket_id='civicmesh-evidence' AND EXISTS (
  SELECT 1 FROM public.evidence e WHERE e.storage_bucket=bucket_id AND e.storage_path=name
  AND e.owner_id=auth.uid() AND e.verified=true
));
