import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { reportApi, type ApiJob, type JobReply } from '../../lib/api/client';
import { useAuth } from '../../lib/supabase/client';
import { WorkflowData } from '../../components/WorkflowData';

export function JobPanel({ jobId }: { jobId: string }) {
  const [job, setJob] = useState<ApiJob>();
  const [error, setError] = useState('');
  const [attempt, setAttempt] = useState(0);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try {
        const next = await reportApi.job(jobId, controller.signal);
        if (controller.signal.aborted) return;
        setJob(next); setError('');
        if (next.status === 'pending' || next.status === 'running') timer = setTimeout(poll, 3000);
      } catch (error) { if (!controller.signal.aborted) setError(error instanceof Error ? error.message : 'Processing status unavailable.'); }
    }
    void poll();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [jobId, attempt]);
  async function answer(reply: JobReply['reply']) {
    if (!job?.checkpoint_id || !job.pending_action || busy) return;
    setBusy(true); setError('');
    try {
      setJob(await reportApi.answer(jobId, { checkpoint_id: job.checkpoint_id,
        interrupt_id: job.pending_action.interrupt_id, reply }));
      setAttempt(value => value + 1);
    } catch (error) { setError(error instanceof Error ? error.message : 'Reply could not be submitted.'); }
    finally { setBusy(false); }
  }
  return <section className="panel"><h2>Processing status</h2>
    {error && <><p role="alert">{error}</p><button className="secondary-button" onClick={() => setAttempt(value => value + 1)}>Reload status</button></>}
    {!job && !error && <p role="status">Loading processing status…</p>}
    {job && <><p role="status">{job.status}</p><p>Job ID: {job.job_id}</p>
      {job.status === 'pending' && <p>Queued for the worker. AI processing is not confirmed until a result appears.</p>}
      {job.status === 'running' && <p>The worker is processing your evidence.</p>}
      {job.error_message && <p role="alert">{job.error_message}</p>}
      {job.status === 'waiting_for_input' && job.pending_action && <PendingReview key={job.checkpoint_id} action={job.pending_action} busy={busy} onAnswer={answer} />}
      {job.status === 'completed' && job.result && <><h3>Result</h3>
        <p>This is an AI-assisted observation or an unsubmitted draft. It is not an official authority response.</p>
        <WorkflowData value={job.result} /></>}
    </>}
  </section>;
}

function PendingReview({ action, busy, onAnswer }: { action: NonNullable<ApiJob['pending_action']>; busy: boolean; onAnswer: (value: JobReply['reply']) => Promise<void> }) {
  const [text, setText] = useState('');
  const [category, setCategory] = useState<'' | 'garbage' | 'water_leak'>('');
  const [latitude, setLatitude] = useState('');
  const [longitude, setLongitude] = useState('');
  const [confirmed, setConfirmed] = useState(false);
  const [error, setError] = useState('');
  async function clarify(event: React.FormEvent) {
    event.preventDefault(); setError('');
    const hasLocation = latitude !== '' || longitude !== '';
    if (hasLocation && (!confirmed || latitude === '' || longitude === '' || !Number.isFinite(Number(latitude)) || !Number.isFinite(Number(longitude)))) {
      setError('Provide and confirm both coordinates.'); return;
    }
    if (!text.trim() && !category && !hasLocation) { setError('Provide an answer before continuing.'); return; }
    await onAnswer({ text: text.trim(), category: category || null,
      location: hasLocation ? { latitude: Number(latitude), longitude: Number(longitude), confirmed: true } : null });
  }
  return <div><h3>{action.kind === 'clarification' ? 'More information needed' : 'Review before continuing'}</h3>
    <WorkflowData value={action.prompt} />
    {action.kind === 'clarification' ? <form onSubmit={clarify}>
      <label>Your answer<textarea maxLength={4000} value={text} onChange={event => setText(event.target.value)} /></label>
      <label>Confirm category<select value={category} onChange={event => setCategory(event.target.value as typeof category)}>
        <option value="">Keep current category</option><option value="garbage">Garbage accumulation</option><option value="water_leak">Water leak</option></select></label>
      <label>Latitude<input type="number" step="any" min="-90" max="90" value={latitude} onChange={event => { setLatitude(event.target.value); setConfirmed(false); }} /></label>
      <label>Longitude<input type="number" step="any" min="-180" max="180" value={longitude} onChange={event => { setLongitude(event.target.value); setConfirmed(false); }} /></label>
      <label className="checkbox-label"><input type="checkbox" checked={confirmed} onChange={event => setConfirmed(event.target.checked)} />I confirm these coordinates.</label>
      {error && <p role="alert">{error}</p>}<button className="primary-button" disabled={busy}>Submit answer</button>
    </form> : <><p>Approval continues this private workflow. It sends no complaint and changes no official status.</p>
      <div className="form-actions"><button className="primary-button" disabled={busy} onClick={() => void onAnswer({ approved: true })}>Approve and continue</button>
        <button className="secondary-button" disabled={busy} onClick={() => void onAnswer({ approved: false })}>Reject</button></div></>}
  </div>;
}

export function JobPage() {
  const { id } = useParams();
  const auth = useAuth();
  if (auth.loading) return <p role="status">Checking session…</p>;
  if (!auth.user) return <div className="screen"><p>Sign in to view this private workflow.</p><Link to="/profile">Sign in</Link></div>;
  return <div className="screen narrow">{id && <JobPanel key={`${auth.user.id}:${id}`} jobId={id} />}</div>;
}
