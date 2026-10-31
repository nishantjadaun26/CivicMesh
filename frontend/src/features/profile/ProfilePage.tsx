import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useAppData, demoUser, contributions } from '../../lib/api/platform';
import { StatusBadge, CategoryIcon } from '../../components/IssueMeta';
import { useAuth } from '../../lib/supabase/client';
import { AuthModal } from '../auth/AuthModal';
import { Icon } from '../../components/Icon';

export function ProfilePage() {
  const { issues, campaigns } = useAppData();
  const { user, isConfigured } = useAuth();
  const [showAuthModal, setShowAuthModal] = useState(false);

  const mine = issues
    .filter(i => i.authorId === demoUser.id)
    .sort((a, b) => Date.parse(b.reportedAt) - Date.parse(a.reportedAt));
  const joined = campaigns.filter(c => c.joined);
  const points = contributions.reduce((n, c) => n + c.points, 0);

  const stats = [
    ['Reports', mine.length],
    ['Under review', mine.filter(i => i.status === 'Under Review').length],
    ['Resolved', mine.filter(i => i.status === 'Resolved').length],
    ['Campaigns joined', joined.length],
    ['Helpful contributions', contributions.length],
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
          <span className="demo-label">Demo account · No sign-in required</span>
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
              ? 'Supabase Auth ready · Sign in to synchronize your reports'
              : 'Authentication is not configured'}
          </strong>
          <span style={{ fontSize: '12px', color: 'var(--muted)' }}>
            {user
              ? 'Access token is automatically attached to backend API requests.'
              : isConfigured
              ? 'Sessions and tokens are managed securely in the browser.'
              : 'Set VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY in your environment. Prototype state is kept safely in browser storage.'}
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
          {user ? user.email?.slice(0, 2).toUpperCase() : 'MK'}
        </span>
        <div>
          <h2>{user ? user.email?.split('@')[0] : demoUser.name}</h2>
          <p>{user ? user.email : `@${demoUser.username}`}</p>
          <span className="help">
            Indiranagar, Bengaluru · Joined {demoUser.joined}
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
                    {i.location} · {new Date(i.reportedAt).toLocaleDateString('en-IN')}
                  </small>
                </span>
                <StatusBadge status={i.status} />
              </Link>
            ))}
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
              ...contributions,
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
          </div>
        </section>

        <aside>
          <div className="panel rewards">
            <h2>Civic points</h2>
            <strong className="points-value">{points}</strong>
            <p>For useful, reviewed contributions.</p>
            <p className="help">
              Demo awards only. No cash value or redemption. New reports earn no automatic points.
            </p>
          </div>

          <div className="panel">
            <h2>Community badges</h2>
            <div className="badge-row">
              <span className="badge-seal">1</span>
              <div>
                <strong>First Report</strong>
                <p>Your first local concern documented.</p>
              </div>
            </div>
            <div className="badge-row">
              <span className="badge-seal">✓</span>
              <div>
                <strong>Neighborhood Helper</strong>
                <p>Useful context and follow-up evidence.</p>
              </div>
            </div>
            <p className="help">Badges reflect the seeded demo contribution history.</p>
          </div>
        </aside>
      </div>

      {/* Supabase Auth Modal */}
      <AuthModal isOpen={showAuthModal} onClose={() => setShowAuthModal(false)} />
    </div>
  );
}
