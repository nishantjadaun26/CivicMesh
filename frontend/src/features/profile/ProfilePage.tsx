import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { reportApi, type ApiReport } from '../../lib/api/client';
import { useAuth } from '../../lib/supabase/client';
import { AuthModal } from '../auth/AuthModal';

function PrivateHistory() {
  const [reports, setReports] = useState<ApiReport[]>([]);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  useEffect(() => {
    const controller = new AbortController();
    setReports([]); setLoading(true); setError('');
    reportApi.list(page, controller.signal).then(setReports).catch(error => {
      if (!controller.signal.aborted) setError(error instanceof Error ? error.message : 'Reports unavailable.');
    }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [page]);
  return <section className="panel"><h2>Your private reports</h2>
    {loading && <p role="status">Loading reports…</p>}
    {error && <p role="alert">{error}</p>}
    {!loading && !error && reports.length === 0 && <p>No reports on this page.</p>}
    <ul>{reports.map(report => <li key={report.id}>
      <Link to={`/reports/${report.id}`}>{report.text.slice(0, 120) || 'Media report'}</Link>
      <p>{report.status} · {new Date(report.created_at).toLocaleString()}</p>
    </li>)}</ul>
    <div className="form-actions"><button className="secondary-button" disabled={page === 1 || loading} onClick={() => setPage(page - 1)}>Previous reports</button>
      <button className="secondary-button" disabled={reports.length < 20 || loading} onClick={() => setPage(page + 1)}>More reports</button></div>
  </section>;
}

export function ProfilePage() {
  const auth = useAuth();
  const [open, setOpen] = useState(false);
  return <div className="screen narrow"><h1>Your account</h1>
    <h2>{auth.user?.email ?? 'Guest'}</h2>
    <button className="primary-button" onClick={() => setOpen(true)}>{auth.user ? 'Manage account' : 'Sign in'}</button>
    {auth.loading ? <p role="status">Checking session…</p> : auth.user
      ? <PrivateHistory key={auth.user.id} /> : <p>Sign in to view your private reports.</p>}
    <p>Verified badges are not configured.</p>
    <AuthModal isOpen={open} onClose={() => setOpen(false)} />
  </div>;
}
