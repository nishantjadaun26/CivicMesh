import { useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import type { Issue } from '../../types/civic';
import { request, uploadEvidence, type ApiFollowUp } from '../../lib/api/client';
import { useAuth } from '../../lib/supabase/client';
import { WorkflowData } from '../../components/WorkflowData';

interface Props { issue: Issue; onClose: () => void; }

function PreviewContents({ issue, onClose }: Props) {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [text, setText] = useState('');
  const [photo, setPhoto] = useState<File>();
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const ticket = useRef<{ file: File; id: string } | undefined>(undefined);
  const submission = useRef<{ body: string; key: string } | undefined>(undefined);
  const owner = useRef(user?.id);
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!user || !photo || !confirmed || busy) return;
    if (owner.current !== user.id) { ticket.current = undefined; submission.current = undefined; owner.current = user.id; }
    setBusy(true); setError('');
    try {
      if (!ticket.current || ticket.current.file !== photo) ticket.current = { file: photo, id: await uploadEvidence(photo) };
      const body = JSON.stringify({ text, evidence_ids: [ticket.current.id], same_location_confirmed: true });
      if (submission.current?.body !== body) submission.current = { body, key: crypto.randomUUID() };
      const result = await request<ApiFollowUp>(`/incidents/${encodeURIComponent(issue.id)}/follow-ups`, {
        method: 'POST', body, headers: { 'Idempotency-Key': submission.current.key },
      }, true);
      navigate(`/jobs/${result.job_id}`);
    } catch (error) { setError(error instanceof Error ? error.message : 'Follow-up could not be submitted.'); }
    finally { setBusy(false); }
  }
  return <section className="issue-preview" aria-label="Issue details">
    <button className="back-button" onClick={onClose}>All nearby issues</button>
    <h2 tabIndex={-1}>{issue.title}</h2><p>{issue.location}</p>
    <h3>Observed condition</h3><p>{issue.observedCondition}</p>
    <h3>Authority status</h3><p>{issue.authorityStatus === 'unknown' ? 'No verified official update recorded.' : issue.authorityStatus}</p>
    {issue.status === 'Community report · unverified'
      ? <p>Community-reported and not independently verified. Reporter identity and uploaded evidence are not public.</p>
      : <p>Approved public record. Private citizen identity and evidence are not published.</p>}
    {issue.timeline.length > 0 && <><h3>Recorded authority updates</h3><WorkflowData value={issue.timeline} /></>}
    {!user ? <Link to="/profile">Sign in to submit follow-up evidence</Link> : <form onSubmit={submit}>
      <h3>Add a private follow-up</h3>
      <p>The assessment uses only your authorized evidence. Without an available baseline it must report insufficient evidence.</p>
      <label>Observation<textarea value={text} maxLength={10000} onChange={event => setText(event.target.value)} /></label>
      <label>Follow-up photo<input type="file" required accept="image/jpeg,image/png,image/webp" onChange={event => setPhoto(event.target.files?.[0])} /></label>
      <label className="checkbox-label"><input type="checkbox" required checked={confirmed} onChange={event => setConfirmed(event.target.checked)} />This is the same location as the original incident.</label>
      <button className="primary-button" disabled={busy}>{busy ? 'Submitting follow-up…' : 'Submit follow-up'}</button>
      {error && <p role="alert">{error}</p>}
    </form>}
  </section>;
}

export function IssuePreview(props: Props) {
  const { user } = useAuth();
  return <PreviewContents key={user?.id ?? 'guest'} {...props} />;
}
