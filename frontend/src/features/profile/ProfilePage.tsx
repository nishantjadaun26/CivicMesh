import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useAppData, guestUser, contributions, getUserCampaignMemberships } from '../../lib/api/platform';
import { StatusBadge, CategoryIcon } from '../../components/IssueMeta';
import { useAuth } from '../../lib/supabase/client';
import { AuthModal } from '../auth/AuthModal';
import { Icon } from '../../components/Icon';

export function ProfilePage() {
  const { issues, campaigns } = useAppData();
  const { user, isConfigured } = useAuth();
  const [showAuthModal, setShowAuthModal] = useState(false);

  const currentUserId = user ? user.id : guestUser.id;
  const memberships = getUserCampaignMemberships(currentUserId);

  const mine = issues
    .filter(i => Boolean(user && i.authorId === user.id))
    .sort((a, b) => Date.parse(b.reportedAt) - Date.parse(a.reportedAt));

  const joined = campaigns.filter(c => memberships.has(c.id));
  const myContributions = contributions;
  const points = myContributions.reduce((n, c) => n + c.points, 0);

  const stats = [
    ['Reports', mine.length],
    ['Under review', mine.filter(i => i.status === 'Under Review').length],
    ['Resolved', mine.filter(i => i.status === 'Resolved').length],
    ['Campaigns joined', joined.length],
    ['Helpful contributions', myContributions.length],
  ];

  return (
    <div className="screen">
      <div className="page-heading">
        <div>
          <h1>Your neighborhood story</h1>
          <p>Every useful contribution helps build a clearer picture.</p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <button
            type="button"
            className="secondary-button"
            onClick={() => setShowAuthModal(true)}
            style={{ fontSize: '12px', minHeight: '36px', padding: '6px 12px' }}
          >
            <Icon name="check" size={14} />
            {user ? 'Account Session' : 'Citizen Auth'}
          </button>
          <span className="demo-label">Sign in to view your private reports</span>
        </div>
      </div>

      {/* Supabase Authentication Status Banner */}
      <div
        className="panel"
        style={{
          padding: '14px 18px',
          marginBottom: '20px',
          background: isConfigured ? '#f4f8f4' : '#faf5ed',
          borderLeft: `4px solid ${isConfigured ? 'var(--green)' : '#c49a6c'}`,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '12px',
        }}
      >
        <div>
          <strong style={{ fontSize: '13px', display: 'block', color: 'var(--ink)' }}>
            {user
              ? `Authenticated via Supabase (${user.email})`
              : isConfigured
              ? 'Supabase Auth ready · Sign in to your account'
              : 'Authentication is not configured'}
          </strong>
          <span style={{ fontSize: '12px', color: 'var(--muted)' }}>
            {user
              ? 'Reports shown here are from this session. Account history is not connected yet.'
              : isConfigured
              ? 'Sessions and tokens are managed securely in the browser.'
              : 'Set VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY in your environment. Private actions require a configured backend.'}
          </span>
        </div>
        <button
          type="button"
          className="secondary-button"
          onClick={() => setShowAuthModal(true)}
          style={{ fontSize: '12px', padding: '6px 14px' }}
        >
          {user ? 'Manage account' : 'Sign in / View auth'}
        </button>
      </div>

      <div className="profile-identity">
        <span className="profile-avatar">
          {user ? user.email?.slice(0, 2).toUpperCase() : '?' }
        </span>
        <div>
          <h2>{user ? user.email?.split('@')[0] : guestUser.name}</h2>
          <p>{user ? user.email : `@${guestUser.username}`}</p>
          <span className="help">
            Your account details come from your authenticated session.
          </span>
        </div>
      </div>

      <dl className="stats-strip">
        {stats.map(([label, value]) => (
          <div key={label}>
            <dt>{label}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>

      <div className="profile-layout">
        <section>
          <div className="panel">
            <h2>Your reports</h2>
            {mine.map(i => (
              <Link
                className="report-link"
                key={i.id}
                to={`/map?issue=${i.id}`}
              >
                <CategoryIcon category={i.category} />
                <span>
                  <strong>{i.title}</strong>
                  <small>
                    {i.location} · {new Date(i.reportedAt).toLocaleDateString('en-IN')} · <span style={{ color: 'var(--accent)', fontWeight: 600 }}>Device-only</span>
                  </small>
                </span>
                <StatusBadge status={i.status} />
              </Link>
            ))}
            {mine.length > 0 && (
              <p className="help" style={{ fontSize: '11px', color: 'var(--muted)', margin: '10px 0 0' }}>
                Reports listed above are stored on this device only and are not account-synchronized.
              </p>
            )}
            {!mine.length && (
              <p>
                No reports yet. <Link to="/report">Report a local issue.</Link>
              </p>
            )}
          </div>

          <div className="panel">
            <h2>Campaigns you’re part of</h2>
            {joined.map(c => (
              <Link
                className="report-link"
                key={c.id}
                to={`/campaigns/${c.id}`}
              >
                <CategoryIcon category={c.category} />
                <span>
                  <strong>{c.title}</strong>
                  <small>{c.location}</small>
                </span>
              </Link>
            ))}
            {!joined.length && (
              <p className="empty-copy">
                You haven’t joined a campaign yet.{' '}
                <Link to="/campaigns">Find a shared cause.</Link>
              </p>
            )}
          </div>

          <div className="panel">
            <h2>Contribution history</h2>
            {[
              ...mine.map(i => ({
                id: i.id,
                title: i.title,
                date: i.reportedAt,
                points: 0,
                reason:
                  'Report submitted. Points are not awarded simply for submitting.',
                issueId: i.id,
              })),
              ...myContributions,
            ]
              .sort((a, b) => Date.parse(b.date) - Date.parse(a.date))
              .map(c => (
                <div className="history-row" key={c.id}>
                  <div>
                    <Link to={`/map?issue=${c.issueId}`}>
                      <strong>{c.title}</strong>
                    </Link>
                    <p>
                      {new Date(c.date).toLocaleDateString('en-IN')} · {c.reason}
                    </p>
                  </div>
                  <span>{c.points ? `+${c.points} pts` : '0 pts'}</span>
                </div>
              ))}
            {mine.length === 0 && myContributions.length === 0 && (
              <p className="empty-copy">No contributions recorded for your account yet.</p>
            )}
          </div>

          {user && (
            <div
              className="panel"
              style={{
                background: '#faf6f0',
                border: '1.5px dashed var(--edge)',
                marginTop: '16px',
                padding: '16px',
              }}
            >
              <h3 style={{ fontSize: '13px', textTransform: 'uppercase', letterSpacing: '0.04em', color: '#7a5229', margin: '0 0 6px 0' }}>
                Demonstration activity is separated
              </h3>
              <p style={{ fontSize: '12px', color: 'var(--muted)', margin: 0, lineHeight: '1.5' }}>
                Sign in to load your account activity when the backend is connected.
              </p>
            </div>
          )}
        </section>

        <aside>
          <div className="panel rewards">
            <h2>Civic points</h2>
            <strong className="points-value">{points}</strong>
            <p>For useful, reviewed contributions.</p>
            <p className="help">
              {user
                ? 'Personal verified civic points. Submitting reports does not award points automatically.'
                : 'Verified contribution rewards are not configured.'}
            </p>
          </div>

          <div className="panel">
            <h2>Community badges</h2>
            <p className="empty-copy">Verified badges are not configured.</p>
          </div>
        </aside>
      </div>

      {/* Supabase Auth Modal */}
      <AuthModal isOpen={showAuthModal} onClose={() => setShowAuthModal(false)} />
    </div>
  );
}
