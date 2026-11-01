import { Link } from 'react-router-dom';
import { Media } from '../../components/Media';
import { useState } from 'react';
import type { Issue, FollowUpUpdate } from '../../types/civic';
import { Icon } from '../../components/Icon';
import { CategoryIcon, StatusBadge } from '../../components/IssueMeta';
import { issueService } from '../../lib/api/issues';

interface Props {
  issue: Issue;
  onClose: () => void;
  onSupport: (id: string) => Promise<void>;
  onUpdate?: (updated: Issue) => void;
}

export function IssuePreview({ issue, onClose, onSupport, onUpdate }: Props) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [followUps, setFollowUps] = useState<FollowUpUpdate[]>(issue.followUps ?? []);
  const [followUpText, setFollowUpText] = useState('');
  const [followUpPhoto, setFollowUpPhoto] = useState<File | null>(null);
  const [submittingFollowUp, setSubmittingFollowUp] = useState(false);
  const [followUpError, setFollowUpError] = useState('');
  const [followUpSuccess, setFollowUpSuccess] = useState(false);

  async function support() {
    setBusy(true);
    setError('');
    try {
      await onSupport(issue.id);
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : 'Could not save your support. Please try again.'
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleFollowUp(e: React.FormEvent) {
    e.preventDefault();
    if (!followUpText.trim()) return;
    setSubmittingFollowUp(true);
    setFollowUpError('');
    setFollowUpSuccess(false);

    try {
      const updated = await issueService.addFollowUp(
        issue.id,
        followUpText,
        followUpPhoto ?? undefined
      );
      setFollowUps(updated.followUps ?? []);
      setFollowUpText('');
      setFollowUpPhoto(null);
      setFollowUpSuccess(true);
      onUpdate?.(updated);
      setTimeout(() => setFollowUpSuccess(false), 3000);
    } catch (err) {
      setFollowUpError(
        err instanceof Error ? err.message : 'Could not submit follow-up update.'
      );
    } finally {
      setSubmittingFollowUp(false);
    }
  }

  return (
    <section className="issue-preview" aria-label="Issue details">
      <button className="back-button" onClick={onClose}>
        <Icon name="arrow" size={18} style={{ transform: 'rotate(180deg)' }} />
        All nearby issues
      </button>

      <div className="preview-top">
        <CategoryIcon category={issue.category} />
        <span>{issue.category}</span>
        <span className="issue-id">{issue.id}</span>
      </div>

      <h2 tabIndex={-1}>{issue.title}</h2>
      <StatusBadge status={issue.status} />

      <p className="preview-location">
        <Icon name="pin" size={18} />
        {issue.location}
      </p>

      <p className="preview-description">{issue.description}</p>

      {issue.photoId ? (
        <Media id={issue.photoId} />
      ) : (
        <div className="evidence-empty">
          <Icon name="search" />
          <span>No photo attached to this demo report.</span>
        </div>
      )}

      {issue.audioId && <Media id={issue.audioId} audio />}

      {issue.campaignId && (
        <Link className="text-button" to={`/campaigns/${issue.campaignId}`}>
          View related campaign
        </Link>
      )}

      {/* Requirement G: Strict separation of Authority Status from Observed Condition */}
      <div className="status-separation-block" style={{ margin: '18px 0', display: 'grid', gap: '12px' }}>
        {/* Authority Status: actual official municipal updates */}
        <div
          className="panel"
          style={{
            margin: 0,
            padding: '14px',
            background: '#f0f5fa',
            borderLeft: '4px solid #246c9c',
            borderRadius: '8px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '6px' }}>
            <Icon name="check" size={15} style={{ color: '#246c9c' }} />
            <strong
              style={{
                fontSize: '11px',
                textTransform: 'uppercase',
                letterSpacing: '0.05em',
                color: '#1a4e70',
              }}
            >
              Authority Status (Official Updates)
            </strong>
          </div>
          <p style={{ margin: 0, fontSize: '13px', color: '#1e3a5f', fontWeight: 600 }}>
            {issue.authorityStatus || 'No official update recorded'}
          </p>
        </div>

        {/* Observed Condition: citizen observations or AI assessment */}
        <div
          className="panel"
          style={{
            margin: 0,
            padding: '14px',
            background: '#fdfbf7',
            borderLeft: '4px solid #c49a6c',
            borderRadius: '8px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '6px' }}>
            <Icon name="pin" size={15} style={{ color: '#c49a6c' }} />
            <strong
              style={{
                fontSize: '11px',
                textTransform: 'uppercase',
                letterSpacing: '0.05em',
                color: '#7a5229',
              }}
            >
              Observed Condition (Citizen & AI Assessment)
            </strong>
          </div>
          <p style={{ margin: 0, fontSize: '13px', color: '#4a3828' }}>
            {issue.observedCondition ||
              issue.extractionResult?.summary ||
              issue.description ||
              'Observed by neighborhood contributor'}
          </p>
          {issue.extractionResult && (
            <div
              style={{
                marginTop: '8px',
                paddingTop: '8px',
                borderTop: '1px solid rgba(0,0,0,0.06)',
                display: 'flex',
                flexWrap: 'wrap',
                gap: '8px',
                fontSize: '11px',
                color: 'var(--muted)',
              }}
            >
              <span>
                Category: <strong>{issue.extractionResult.detectedCategory}</strong> (
                {(issue.extractionResult.confidence * (issue.extractionResult.confidence <= 1 ? 100 : 1)).toFixed(0)}%)
              </span>
              <span>
                Urgency: <strong>{issue.extractionResult.suggestedUrgency}</strong>
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Approved public information indicator */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          fontSize: '11px',
          color: 'var(--muted)',
          margin: '10px 0',
        }}
      >
        <Icon name="check" size={13} />
        <span>Approved public record · Private reporter identity is protected.</span>
      </div>

      <div className="reporter">
        <span className="small-avatar">
          {issue.reporter
            .split(' ')
            .map(s => s[0])
            .join('')}
        </span>
        <div>
          <strong>{issue.reporter}</strong>
          <span>
            Reported{' '}
            {new Date(issue.reportedAt).toLocaleDateString('en-IN', {
              day: 'numeric',
              month: 'short',
              year: 'numeric',
            })}
          </span>
        </div>
      </div>

      <div className="community-support">
        <Icon name="people" />
        <span>
          <strong>{issue.supporters}</strong> neighbors support this report
        </span>
      </div>

      <button
        className={`primary-button support-button ${issue.supported ? 'supported' : ''}`}
        aria-pressed={issue.supported}
        disabled={busy}
        onClick={support}
      >
        <Icon name={issue.supported ? 'check' : 'heart'} size={19} />
        {busy ? 'Saving…' : issue.supported ? 'Supported · Undo' : 'Support this report'}
      </button>

      {error && (
        <p className="error-text" role="alert">
          {error}
        </p>
      )}

      {/* Requirement G: Timeline of supported updates */}
      <div
        className="follow-up-section"
        style={{
          marginTop: '20px',
          paddingTop: '16px',
          borderTop: '1px solid var(--edge)',
        }}
      >
        <h3 style={{ fontSize: '15px', fontWeight: 800, marginBottom: '10px' }}>
          Timeline of Updates ({followUps.length})
        </h3>
        {followUps.length === 0 ? (
          <p style={{ fontSize: '12px', color: 'var(--muted)', margin: '6px 0 14px' }}>
            No citizen follow-ups yet. Have you checked this location recently?
          </p>
        ) : (
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              gap: '10px',
              marginBottom: '14px',
            }}
          >
            {followUps.map(fu => (
              <div
                key={fu.id}
                style={{
                  padding: '10px 12px',
                  background: 'var(--ground)',
                  borderRadius: '8px',
                  border: '1px solid var(--edge)',
                  fontSize: '13px',
                }}
              >
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    marginBottom: '4px',
                    fontSize: '11px',
                    color: 'var(--muted)',
                  }}
                >
                  <strong>{fu.author}</strong>
                  <time>
                    {new Date(fu.createdAt).toLocaleDateString('en-IN', {
                      day: 'numeric',
                      month: 'short',
                    })}
                  </time>
                </div>
                <p style={{ margin: 0, color: 'var(--ink)' }}>{fu.text}</p>
                {fu.photoUrl && (
                  <img
                    src={fu.photoUrl}
                    alt="Citizen follow-up evidence"
                    style={{
                      marginTop: '8px',
                      maxWidth: '100%',
                      maxHeight: '140px',
                      borderRadius: '6px',
                      objectFit: 'cover',
                    }}
                  />
                )}
              </div>
            ))}
          </div>
        )}

        {/* Requirement G: Follow-up text/photo submission */}
        <form
          onSubmit={handleFollowUp}
          style={{
            padding: '12px',
            background: 'var(--ground)',
            borderRadius: '8px',
            border: '1px dashed var(--edge)',
          }}
        >
          <h4 style={{ fontSize: '13px', fontWeight: 700, margin: '0 0 8px 0' }}>
            Submit a follow-up update
          </h4>
          <textarea
            rows={2}
            value={followUpText}
            onChange={e => setFollowUpText(e.target.value)}
            placeholder="Share current conditions or repair progress…"
            style={{
              width: '100%',
              padding: '8px 10px',
              borderRadius: '6px',
              border: '1px solid var(--edge)',
              fontSize: '13px',
              background: 'var(--surface)',
              resize: 'vertical',
            }}
          />
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              marginTop: '8px',
              flexWrap: 'wrap',
              gap: '8px',
            }}
          >
            <label
              style={{
                fontSize: '12px',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                cursor: 'pointer',
                margin: 0,
              }}
            >
              <Icon name="plus" size={14} />
              <span>{followUpPhoto ? followUpPhoto.name : 'Add photo (optional)'}</span>
              <input
                type="file"
                accept="image/jpeg,image/png,image/webp"
                style={{ display: 'none' }}
                onChange={e => {
                  const file = e.target.files?.[0];
                  if (file) {
                    if (file.size > 8 * 1024 * 1024) {
                      setFollowUpError('Photo must be smaller than 8 MB.');
                      return;
                    }
                    setFollowUpPhoto(file);
                    setFollowUpError('');
                  }
                }}
              />
            </label>
            <button
              type="submit"
              className="secondary-button"
              disabled={submittingFollowUp || !followUpText.trim()}
              style={{ padding: '6px 14px', fontSize: '12px', minHeight: '36px' }}
            >
              {submittingFollowUp ? 'Posting…' : 'Post update'}
            </button>
          </div>
          {followUpError && (
            <p className="error-text" role="alert" style={{ fontSize: '12px', marginTop: '6px' }}>
              {followUpError}
            </p>
          )}
          {followUpSuccess && (
            <p style={{ fontSize: '12px', color: 'var(--green)', marginTop: '6px' }}>
              Follow-up update submitted.
            </p>
          )}
        </form>
      </div>

      <p className="fine-print">
        Community activity is illustrative. This report has not been officially verified.
      </p>
    </section>
  );
}
