import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { reportApi, type ApiReport } from '../../lib/api/client';
import { useAuth } from '../../lib/supabase/client';
import { JobPanel } from './JobPanel';

function PrivateReport({ reportId }: { reportId: string }) {
  const [report, setReport] = useState<ApiReport>();
  const [error, setError] = useState('');
  const [removingShare, setRemovingShare] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    reportApi.get(reportId, controller.signal).then(setReport).catch(error => {
      if (!controller.signal.aborted) setError(error instanceof Error ? error.message : 'Report unavailable.');
    });
    return () => controller.abort();
  }, [reportId]);
  return <div className="screen narrow"><h1>Private report</h1>
    {error && <p role="alert">{error}</p>}
    {!report && !error && <p role="status">Loading report…</p>}
    {report && <><p>Report ID: {report.id}</p>
      {report.public_incident_id
        ? <><p>This report is shared on the community map as an unverified report. <Link to={`/map?issue=${encodeURIComponent(report.public_incident_id)}`}>View it on the map</Link></p>
          <button className="text-button" type="button" disabled={removingShare} onClick={async () => {
            setRemovingShare(true); setError('');
            try {
              await reportApi.removeMapSharing(report.id);
              setReport({ ...report, public_incident_id: null });
            } catch (failure) {
              setError(failure instanceof Error ? failure.message : 'Map sharing could not be removed.');
            } finally { setRemovingShare(false); }
          }}>{removingShare ? 'Removing from map…' : 'Remove from map'}</button></>
        : <p>This report is private and does not appear on the community map.</p>}
      <h2>Your original observation</h2><p style={{ whiteSpace: 'pre-wrap' }}>{report.text || 'Media report'}</p>
      {report.job_id ? <JobPanel jobId={report.job_id} /> : <p role="alert">This report has no processing job. Contact the project owner.</p>}</>}
    <Link to="/profile">Your reports</Link>
  </div>;
}

export function ReportDetail({ reportId }: { reportId?: string }) {
  const params = useParams();
  const auth = useAuth();
  const id = reportId ?? params.id;
  if (auth.loading) return <p role="status">Checking session…</p>;
  if (!auth.user) return <div className="screen"><p>Sign in to view this private report.</p><Link to="/profile">Sign in</Link></div>;
  return id ? <PrivateReport key={`${auth.user.id}:${id}`} reportId={id} /> : <p>Report ID is missing.</p>;
}
