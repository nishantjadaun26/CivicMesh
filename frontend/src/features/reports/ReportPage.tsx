import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { categories, MAP_CENTER } from '../../types/civic';
import { citizenService, useAppData, type ReportDraft, type SubmissionProcessingStatus } from '../../lib/api/platform';
import { LocationPicker } from '../../components/map/LocationPicker';
import { VoiceRecorder } from './VoiceRecorder';
import { ReportDetail } from './ReportDetail';
import { useAuth } from '../../lib/supabase/client';
import type { ApiReport } from '../../lib/api/client';

function ReportForm() {
  const [params] = useSearchParams();
  const { campaigns } = useAppData();
  const [step, setStep] = useState(0);
  const [locationConfirmed, setLocationConfirmed] = useState(false);
  const [draft, setDraft] = useState<ReportDraft>({
    title: '',
    description: '',
    category: 'Garbage accumulation',
    location: '',
    coordinates: MAP_CENTER,
    evidenceConsent: false,
    campaignId: campaigns.some(c => c.id === params.get('campaign'))
      ? params.get('campaign')!
      : undefined,
  });
  const [photo, setPhoto] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState<SubmissionProcessingStatus | null>(null);
  const [result, setResult] = useState<ApiReport | null>(null);

  useEffect(() => () => {
    if (photo) URL.revokeObjectURL(photo);
  }, [photo]);

  function advance() {
    setError('');
    if (step === 0 && (!draft.location.trim() || !locationConfirmed)) {
      setError('Add a location name and confirm the coordinates.');
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
    setProgress(null);
    try {
      const issue = await citizenService.createReport(draft, p => {
        setProgress(p);
      });
      setResult(issue);
    } catch (e) {
      setProgress(null);
      setError(
        e instanceof Error
          ? e.message
          : 'Submission failed. Your report is still here; please retry.'
      );
    } finally {
      setBusy(false);
    }
  }

  if (result) return <ReportDetail reportId={result.id} />;

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
                onChange={coordinates => { setDraft({ ...draft, coordinates }); setLocationConfirmed(false); }}
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

          {step === 0 && <label className="checkbox-label"><input type="checkbox" checked={locationConfirmed} onChange={event => setLocationConfirmed(event.target.checked)} />I have confirmed the latitude and longitude.</label>}

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
                      file.size > 10 * 1024 * 1024
                    ) {
                      setError('Choose a JPEG, PNG or WebP image smaller than 10 MiB.');
                      e.target.value = '';
                      return;
                    }
                    setDraft({ ...draft, photo: file });
                    setPhoto(URL.createObjectURL(file));
                    setError('');
                  }}
                />
                <span>JPEG, PNG or WebP · Up to 10 MiB. Choose again to replace.</span>
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
              <VoiceRecorder value={draft.audio} onChange={audio => setDraft(d => ({ ...d, audio }))} />
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
                  {categories.filter(c => c === 'Garbage accumulation' || c === 'Water leak').map(c => (
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

              {busy && progress && (
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
                    Step {progress.step}/2: {progress.message}
                  </span>
                </div>
              )}

              <p className="notice">
                {busy
                  ? progress
                    ? progress.isBackendConnected
                      ? 'Submitting report to backend services…'
                      : 'Preparing your report…'
                    : 'Preparing your report…'
                  : 'This report has not been sent yet. Review your details before submitting.'}
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
                {busy ? 'Submitting report…' : 'Submit report'}
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

export function ReportPage() {
  const { user } = useAuth();
  return <ReportForm key={user?.id ?? 'guest'} />;
}
