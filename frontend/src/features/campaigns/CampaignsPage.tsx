import { useState, useRef } from 'react';
import { Link, useParams } from 'react-router-dom';
import { citizenService, useAppData, getUserCampaignMemberships, guestUser } from '../../lib/api/platform';
import { CategoryIcon, StatusBadge } from '../../components/IssueMeta';
import { Media } from '../../components/Media';
import { useAuth } from '../../lib/supabase/client';

export function CampaignsPage() {
  const { campaigns, issues } = useAppData();
  const { user } = useAuth();
  const { id } = useParams();
  const [message, setMessage] = useState('');
  const [search, setSearch] = useState('');

  const activeUserId = user ? user.id : guestUser.id;

  // Derive user-specific campaign membership scoped to active user
  const memberships = getUserCampaignMemberships(activeUserId);

  const isJoined = (cid: string) => memberships.has(cid);

  const campaign = campaigns.find(c => c.id === id);

  const pendingRef = useRef<Set<string>>(new Set());
  const [pendingId, setPendingId] = useState<string | null>(null);

  async function join(cid: string) {
    if (pendingRef.current.has(cid)) return;
    pendingRef.current.add(cid);
    setPendingId(cid);
    setMessage('');
    try {
      await citizenService.toggleCampaign(cid);
      setMessage('Campaign participation updated on this device.');
    } catch (e) {
      setMessage(e instanceof Error ? e.message : 'Could not update participation. Try again.');
    } finally {
      pendingRef.current.delete(cid);
      setPendingId(null);
    }
  }

  async function share() {
    const url = location.href;
    try {
      if (navigator.share) {
        await navigator.share({ title: campaign?.title, url });
        setMessage('Share dialog opened.');
      } else {
        await navigator.clipboard.writeText(url);
        setMessage('Campaign link copied.');
      }
    } catch {
      setMessage('Sharing unavailable. Copy the campaign URL below.');
    }
  }

  const related = issues.filter(i => i.campaignId === campaign?.id);

  if (id && !campaign) {
    return (
      <div className="screen">
        <h1>Campaign not found</h1>
        <Link to="/campaigns">Browse campaigns</Link>
      </div>
    );
  }

  return (
    <div className="screen">
      <div className="page-heading">
        <div>
          <h1>{campaign ? campaign.title : 'Small voices. Shared purpose.'}</h1>
          <p>
            {campaign
              ? campaign.location
              : 'Join your neighbors around the issues that keep coming back.'}
          </p>
        </div>
        <span className="demo-label">Community campaigns · Demo</span>
      </div>

      {campaigns.length === 0 && <p role="status" className="panel">Campaign services are not configured. No campaigns have been loaded.</p>}

      {message && (
        <p role="status" className="notice">
          {message}
        </p>
      )}

      {campaign ? (
        <>
          <Link className="text-button" to="/campaigns">
            ← All campaigns
          </Link>
          <div className="campaign-detail-layout">
            <section>
              <div className="panel">
                <CategoryIcon category={campaign.category} />
                <h2>About this campaign</h2>
                <p>{campaign.description}</p>
                <div className="campaign-numbers">
                  <span>
                    <strong>{related.length}</strong> related reports
                  </span>
                  <span>
                    <strong>
                      {
                        new Set([
                          ...campaign.followers,
                          ...related.map(i => i.authorId),
                          ...(isJoined(campaign.id) ? [activeUserId] : []),
                        ]).size
                      }
                    </strong>{' '}
                    contributors
                  </span>
                </div>
                <div className="form-actions">
                  <button
                    className="primary-button"
                    disabled={pendingId === campaign.id}
                    aria-busy={pendingId === campaign.id}
                    aria-pressed={isJoined(campaign.id)}
                    aria-label={
                      pendingId === campaign.id
                        ? `Updating membership for ${campaign.title} campaign`
                        : isJoined(campaign.id)
                        ? `Leave ${campaign.title} campaign`
                        : `Join ${campaign.title} campaign`
                    }
                    onClick={() => join(campaign.id)}
                  >
                    {pendingId === campaign.id
                      ? 'Updating…'
                      : isJoined(campaign.id)
                      ? 'Leave campaign'
                      : 'Join campaign'}
                  </button>
                  <Link
                    className="secondary-button"
                    to={`/report?campaign=${campaign.id}`}
                  >
                    Contribute a report
                  </Link>
                  <button className="secondary-button" onClick={share}>
                    Share campaign
                  </button>
                </div>
                <label>
                  Campaign link
                  <input
                    readOnly
                    value={location.href}
                    onFocus={e => e.target.select()}
                  />
                </label>
              </div>

              <section className="panel">
                <h2>Evidence from neighbors</h2>
                <p className="help">
                  Only photographs with explicit campaign-sharing consent appear here.
                </p>
                <div className="evidence-gallery">
                  {related
                    .filter(i => i.photoId && i.evidenceConsent)
                    .map(i => (
                      <figure key={i.id}>
                        <Media id={i.photoId!} />
                        <figcaption>{i.title}</figcaption>
                      </figure>
                    ))}
                </div>
                {!related.some(i => i.photoId && i.evidenceConsent) && (
                  <p className="empty-copy">
                    No shared photographs yet. Contribute a report and choose whether to share its photo.
                  </p>
                )}
              </section>

              <section className="panel">
                <h2>Related reports</h2>
                {related.map(i => (
                  <Link
                    className="report-link"
                    key={i.id}
                    to={`/map?issue=${i.id}`}
                  >
                    <CategoryIcon category={i.category} />
                    <span>
                      <strong>{i.title}</strong>
                      <small>{i.location}</small>
                    </span>
                    <StatusBadge status={i.status} />
                  </Link>
                ))}
              </section>
            </section>

            <aside className="panel timeline">
              <h2>Campaign updates</h2>
              <p className="notice">
                Illustrative community activity. No official authority verification.
              </p>
              <ol>
                <li>
                  <strong>Neighborhood concern documented</strong>
                  <p>
                    {campaign.updatedAt} · Related citizen reports brought together in this demo.
                  </p>
                </li>
                {related.map(i => (
                  <li key={i.id}>
                    <strong>{i.title}</strong>
                    <p>
                      {new Date(i.reportedAt).toLocaleDateString('en-IN')} · {i.reporter}
                    </p>
                  </li>
                ))}
                {isJoined(campaign.id) && (
                  <li>
                    <strong>You joined this campaign</strong>
                    <p>You can follow its local updates here.</p>
                  </li>
                )}
              </ol>
            </aside>
          </div>
        </>
      ) : (
        <>
          <label className="campaign-search">
            Find a campaign
            <input
              type="search"
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Search a concern or neighborhood"
            />
          </label>
          <div className="campaign-feed">
            {campaigns
              .filter(c =>
                `${c.title} ${c.location}`
                  .toLowerCase()
                  .includes(search.toLowerCase())
              )
              .map((c, index) => {
                const reports = issues.filter(i => i.campaignId === c.id);
                return (
                  <article className="campaign-card" key={c.id}>
                    <div
                      className={`campaign-art art-${index}`}
                      aria-hidden="true"
                    >
                      {reports.some(i => i.photoId && i.evidenceConsent) ? (
                        <Media
                          id={
                            reports.find(i => i.photoId && i.evidenceConsent)!.photoId!
                          }
                        />
                      ) : (
                        <>
                          <CategoryIcon category={c.category} />
                          <span>{c.category}</span>
                        </>
                      )}
                    </div>
                    <div className="campaign-card-body">
                      <span className="help">
                        {c.location} · Gathering evidence
                      </span>
                      <h2>
                        <Link to={`/campaigns/${c.id}`}>{c.title}</Link>
                      </h2>
                      <p>{c.description}</p>
                      <div className="campaign-numbers">
                        <span>
                          <strong>{reports.length}</strong> reports
                        </span>
                        <span>
                          <strong>
                            {
                              new Set([
                                ...c.followers,
                                ...reports.map(i => i.authorId),
                                ...(isJoined(c.id) ? [activeUserId] : []),
                              ]).size
                            }
                          </strong>{' '}
                          contributors
                        </span>
                      </div>
                      <p className="help">Latest demo activity · {c.updatedAt}</p>
                      <div className="form-actions">
                        <Link
                          className="secondary-button"
                          to={`/campaigns/${c.id}`}
                        >
                          View campaign
                        </Link>
                        <button
                          className="primary-button"
                          disabled={pendingId === c.id}
                          aria-busy={pendingId === c.id}
                          aria-pressed={isJoined(c.id)}
                          aria-label={
                            pendingId === c.id
                              ? `Updating membership for ${c.title} campaign`
                              : isJoined(c.id)
                              ? `Leave ${c.title} campaign`
                              : `Join ${c.title} campaign`
                          }
                          onClick={() => join(c.id)}
                        >
                          {pendingId === c.id
                            ? 'Updating…'
                            : isJoined(c.id)
                            ? 'Leave campaign'
                            : 'Join campaign'}
                        </button>
                      </div>
                    </div>
                  </article>
                );
              })}
          </div>
          {!campaigns.some(c =>
            `${c.title} ${c.location}`
              .toLowerCase()
              .includes(search.toLowerCase())
          ) && (
            <div className="empty-state">
              <h2>No campaigns found</h2>
              <button
                className="secondary-button"
                onClick={() => setSearch('')}
              >
                Clear search
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
