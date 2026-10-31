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
