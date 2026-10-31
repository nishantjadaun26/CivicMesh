import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { categories, DEMO_CENTER, type Issue } from '../../types/civic';
import { citizenService, useAppData, type ReportDraft, type SubmissionProcessingStatus } from '../../lib/api/platform';
import { LocationPicker } from '../../components/map/LocationPicker';
import { VoiceRecorder } from './VoiceRecorder';
import { issueService } from '../../lib/api/issues';

export function ReportPage() {
  const [params] = useSearchParams();
  const { campaigns } = useAppData();
  const [step, setStep] = useState(0);
  const [draft, setDraft] = useState<ReportDraft>({
    title: '',
    description: '',
    category: 'Roads',
    location: 'Indiranagar, Bengaluru',
    coordinates: DEMO_CENTER,
    evidenceConsent: false,
    campaignId: campaigns.some(c => c.id === params.get('campaign'))
      ? params.get('campaign')!
      : undefined,
  });
  const [photo, setPhoto] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState<SubmissionProcessingStatus | null>(null);
  const [result, setResult] = useState<Issue | null>(null);
  const [clarificationAnswers, setClarificationAnswers] = useState<Record<string, string>>({});
  const [clarificationSubmitted, setClarificationSubmitted] = useState(false);

  useEffect(() => () => {
    if (photo) URL.revokeObjectURL(photo);
  }, [photo]);

  function advance() {
    setError('');
    if (step === 0 && !draft.location.trim()) {
      setError('Add a location name.');
      return;
    }
    if (step === 1 && !draft.photo) {
      setError('Add a photograph of the issue.');
      return;
    }
    setStep(s => s + 1);
  }

  async function submit() {
    if (busy) return;
    setBusy(true);
    setError('');
    try {
      const issue = await citizenService.createReport(draft, p => {
        setProgress(p);
      });
      setResult(issue);
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : 'Submission failed. Your report is still here; please retry.'
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleClarificationSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!result) return;
    try {
      const updated = await issueService.submitClarification(result.id, clarificationAnswers);
      setResult(updated);
      setClarificationSubmitted(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not submit clarification.');
    }
  }

  // Success and Extraction Processing Result View
  if (result) {
    return (
      <div className="screen narrow">
        <div className="success-mark">✓</div>
        <h1>Report received.</h1>
        <p className="intro">Thank you for looking out for your neighborhood.</p>

        {/* Processing Sequence & Job Details */}
        <div className="panel" style={{ borderLeft: '4px solid var(--accent)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h2>{result.id}</h2>
            {result.jobId && (
              <span style={{ fontSize: '12px', fontFamily: 'monospace', color: 'var(--muted)' }}>
                Job: {result.jobId}
              </span>
            )}
          </div>
          <p style={{ marginTop: '8px' }}>
            <strong>Status:</strong> {result.status}
          </p>

          {/* AI Extraction Result */}
          {result.extractionResult && (
            <div style={{ margin: '14px 0', padding: '12px', background: 'var(--ground)', borderRadius: '8px' }}>
              <div style={{ fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--muted)', fontWeight: 800 }}>
                Automated Extraction Result
              </div>
              <p style={{ fontSize: '13px', margin: '6px 0', fontWeight: 600 }}>
                {result.extractionResult.summary}
              </p>
              <div style={{ display: 'flex', gap: '12px', fontSize: '12px', color: 'var(--muted)' }}>
                <span>Confidence: {(result.extractionResult.confidence * 100).toFixed(0)}%</span>
                <span>Urgency: {result.extractionResult.suggestedUrgency}</span>
              </div>
            </div>
          )}

          {/* Requirement G: Authority Status vs Observed Condition */}
          <div style={{ marginTop: '12px', paddingTop: '12px', borderTop: '1px solid var(--edge)', display: 'grid', gap: '10px' }}>
            <div>
              <span style={{ fontSize: '11px', fontWeight: 800, color: '#9c5b28' }}>Observed Condition:</span>
              <p style={{ fontSize: '13px', margin: '2px 0' }}>{result.observedCondition}</p>
            </div>
            <div>
              <span style={{ fontSize: '11px', fontWeight: 800, color: 'var(--blue)' }}>Authority Status:</span>
              <p style={{ fontSize: '13px', margin: '2px 0', color: 'var(--muted)' }}>{result.authorityStatus}</p>
            </div>
          </div>
        </div>

        {/* Requirement F: Clarification Questions Screen */}
        {result.clarificationQuestions && result.clarificationQuestions.length > 0 && !clarificationSubmitted && (
          <div className="panel" style={{ background: '#fdf7ee', border: '1.5px solid #d4b58c' }}>
            <h3 style={{ fontSize: '16px', color: '#684022', marginBottom: '8px' }}>
              Clarification Needed by AI Workflow
            </h3>
            <p style={{ fontSize: '12px', color: 'var(--muted)', marginBottom: '14px' }}>
              To help authorities route and prioritize this issue quickly, please answer this question:
            </p>
            <form onSubmit={handleClarificationSubmit}>
              {result.clarificationQuestions.map(q => (
                <div key={q.id} style={{ marginBottom: '14px' }}>
                  <label style={{ fontSize: '13px', fontWeight: 700, display: 'block', marginBottom: '8px' }}>
                    {q.question}
                  </label>
                  {q.type === 'choice' && q.options ? (
                    <div style={{ display: 'grid', gap: '8px' }}>
                      {q.options.map(opt => (
                        <label
                          key={opt}
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '8px',
                            margin: 0,
                            padding: '8px 12px',
                            background: 'var(--surface)',
                            border: '1px solid var(--edge)',
                            borderRadius: '6px',
                            cursor: 'pointer',
                          }}
                        >
                          <input
                            type="radio"
                            name={q.id}
                            value={opt}
                            checked={clarificationAnswers[q.id] === opt}
                            onChange={() => setClarificationAnswers(prev => ({ ...prev, [q.id]: opt }))}
                          />
                          <span style={{ fontSize: '13px' }}>{opt}</span>
                        </label>
                      ))}
                    </div>
                  ) : (
                    <input
                      type="text"
                      placeholder="Your answer…"
                      value={clarificationAnswers[q.id] ?? ''}
                      onChange={e => setClarificationAnswers(prev => ({ ...prev, [q.id]: e.target.value }))}
                      style={{ width: '100%', height: '42px', padding: '0 10px', borderRadius: '6px', border: '1px solid var(--edge)' }}
                    />
                  )}
                </div>
              ))}
              <button type="submit" className="secondary-button" style={{ marginTop: '8px' }}>
                Submit clarification
              </button>
            </form>
          </div>
        )}

        {clarificationSubmitted && (
          <p role="status" style={{ color: 'var(--green)', fontSize: '13px', margin: '12px 0' }}>
            ✓ Clarification recorded. Resumed processing with updated extraction details.
          </p>
        )}

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '12px', marginTop: '20px' }}>
          <Link className="primary-button" to={`/map?issue=${result.id}`}>
            View submitted report
          </Link>
          <Link className="text-button" to="/profile">
            View contribution history
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="screen">
      <div className="page-heading">
        <div>
          <h1>Report a local issue</h1>
          <p>A location. A photo. A clearer picture for your community.</p>
        </div>
        <span className="demo-label">Citizen submission</span>
      </div>

      <ol className="steps" aria-label="Reporting progress">
        {['Location', 'Evidence', 'Category', 'Review'].map((s, i) => (
          <li key={s} aria-current={step === i ? 'step' : undefined}>
            {s}
          </li>
        ))}
      </ol>

      <div className="report-layout">
        <section className="panel report-form">
          <h2>
            {
              [
                'Where is the issue?',
                'Show what’s happening',
                'Choose the issue category',
                'Review your report',
              ][step]
            }
          </h2>

          {/* STEP 0: Location Confirmation */}
          {step === 0 && (
            <>
              <LocationPicker
                value={draft.coordinates}
                onChange={coordinates => setDraft({ ...draft, coordinates })}
              />
              <label>
                Location name
                <input
                  value={draft.location}
                  onChange={e => setDraft({ ...draft, location: e.target.value })}
                  maxLength={160}
                />
              </label>
            </>
          )}

          {/* STEP 1: Photo & Spoken/Audio Note Evidence */}
          {step === 1 && (
            <>
              <label className="upload-control">
                Photograph (required)
                <input
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  onChange={e => {
                    const file = e.target.files?.[0];
                    if (!file) return;
                    if (
                      !['image/jpeg', 'image/png', 'image/webp'].includes(file.type) ||
                      file.size > 8 * 1024 * 1024
                    ) {
                      setError('Choose a JPEG, PNG or WebP image smaller than 8 MB.');
                      e.target.value = '';
                      return;
                    }
                    setDraft({ ...draft, photo: file });
                    setPhoto(URL.createObjectURL(file));
                    setError('');
                  }}
                />
                <span>JPEG, PNG or WebP · Up to 8 MB. Choose again to replace.</span>
              </label>

              {photo && (
                <>
                  <img
                    className="upload-preview"
                    src={photo}
                    alt="Selected report photograph"
                  />
                  <button
                    type="button"
                    className="text-button"
                    onClick={() => {
                      setPhoto('');
                      setDraft({ ...draft, photo: undefined });
                    }}
                  >
                    Remove photo
                  </button>
                </>
              )}

              <label>
                Description (optional)
                <textarea
                  rows={4}
                  maxLength={2000}
                  value={draft.description}
                  placeholder="What should your neighbors know?"
                  onChange={e => setDraft({ ...draft, description: e.target.value })}
                />
              </label>

              {/* MediaRecorder & Audio File fallback */}
              <VoiceRecorder onChange={audio => setDraft(d => ({ ...d, audio }))} />
            </>
          )}

          {/* STEP 2: Category & Campaign */}
          {step === 2 && (
            <>
              <label>
                Category
                <select
                  value={draft.category}
                  onChange={e =>
                    setDraft({ ...draft, category: e.target.value as ReportDraft['category'] })
                  }
                >
                  {categories.map(c => (
                    <option key={c}>{c}</option>
                  ))}
                </select>
              </label>

              <label>
                Short title (optional)
                <input
                  value={draft.title}
                  maxLength={120}
                  onChange={e => setDraft({ ...draft, title: e.target.value })}
                  placeholder="e.g. Garbage accumulation near crossing"
                />
              </label>

              <label>
                Related campaign
                <select
                  value={draft.campaignId ?? ''}
                  onChange={e =>
                    setDraft({
                      ...draft,
                      campaignId: e.target.value || undefined,
                      evidenceConsent: false,
                    })
                  }
                >
                  <option value="">No campaign</option>
                  {campaigns.map(c => (
                    <option value={c.id} key={c.id}>
                      {c.title}
                    </option>
                  ))}
                </select>
              </label>

              {draft.campaignId && (
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={draft.evidenceConsent}
                    onChange={e => setDraft({ ...draft, evidenceConsent: e.target.checked })}
                  />
                  I allow this photograph to appear in the selected campaign’s evidence gallery.
                </label>
              )}
              <p className="help">
                Without consent, your photograph stays with this report and is excluded from campaign galleries.
              </p>
            </>
          )}

          {/* STEP 3: Review & Submission */}
          {step === 3 && (
            <>
              <img
                className="upload-preview"
                src={photo}
                alt="Photograph to submit"
              />
              <dl className="review-list">
                <dt>Location</dt>
                <dd>
                  {draft.location} ({draft.coordinates.lat.toFixed(5)},{' '}
                  {draft.coordinates.lng.toFixed(5)})
                </dd>
                <dt>Category</dt>
                <dd>{draft.category}</dd>
                <dt>Title</dt>
                <dd>{draft.title || 'Generated from category and location'}</dd>
                <dt>Description</dt>
                <dd>{draft.description || 'No description added'}</dd>
                <dt>Voice note</dt>
                <dd>{draft.audio ? 'Attached' : 'Not attached'}</dd>
                <dt>Campaign evidence</dt>
                <dd>{draft.evidenceConsent ? 'Consent given' : 'Not shared'}</dd>
              </dl>

              {progress && (
                <div
                  style={{
                    padding: '12px 14px',
                    margin: '14px 0',
                    background: 'var(--ground)',
                    borderRadius: '8px',
                    fontSize: '12px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '10px',
                  }}
                >
                  <div
                    style={{
                      width: '14px',
                      height: '14px',
                      border: '2px solid var(--accent)',
                      borderTopColor: 'transparent',
                      borderRadius: '50%',
                      animation: 'spin 1s linear infinite',
                    }}
                  />
                  <span>
                    Step {progress.step}/6: {progress.message}
                  </span>
                </div>
              )}

              <p className="notice">
                Submissions are stored securely. Backend verification runs automated category extraction and checks idempotency.
              </p>
            </>
          )}

          {error && (
            <p role="alert" className="error-text">
              {error}
            </p>
          )}

          <div className="form-actions">
            {step > 0 && (
              <button
                type="button"
                className="secondary-button"
                disabled={busy}
                onClick={() => setStep(s => s - 1)}
              >
                Back
              </button>
            )}
            {step < 3 ? (
              <button type="button" className="primary-button" onClick={advance}>
                {step === 0 ? 'Confirm location' : 'Continue'}
              </button>
            ) : (
              <button
                type="button"
                className="primary-button"
                disabled={busy}
                onClick={submit}
              >
                {busy ? 'Saving report…' : 'Submit report'}
              </button>
            )}
          </div>
        </section>

        <aside className="report-guidance">
          <h2>A useful report makes a difference.</h2>
          <p>Place the pin at the actual issue, even if you’re reporting from somewhere else.</p>
          <p>Photograph the problem clearly. Avoid faces, vehicle plates and private information.</p>
          <p>You can review and edit everything before submitting.</p>
        </aside>
      </div>
    </div>
  );
}
