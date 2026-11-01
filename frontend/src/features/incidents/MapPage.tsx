import { useEffect, useRef, useState } from 'react';
import { Link, useSearchParams, useParams } from 'react-router-dom';
import { MapCanvas } from '../../components/map/MapCanvas';
import { Icon } from '../../components/Icon';
import { CategoryIcon, StatusBadge, categoryIcons } from '../../components/IssueMeta';
import { categories, type Category, type Issue } from '../../types/civic';
import { issueService } from '../../lib/api/issues';
import { IssuePreview } from './IssuePreview';

export function MapPage() {
  const [issues, setIssues] = useState<Issue[]>([]);
  const [listMeta, setListMeta] = useState<{ source: 'api' | 'local'; backendFailed?: boolean }>({
    source: 'local',
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [attempt, setAttempt] = useState(0);
  const [params, setParams] = useSearchParams();
  const [view, setView] = useState<'map' | 'list'>('map');
  const previousTrigger = useRef<HTMLElement | null>(null);

  const query = params.get('q') ?? '';
  const rawCategory = params.get('category');
  const category = categories.includes(rawCategory as Category)
    ? (rawCategory as Category)
    : 'All';
  const status = [
    'all',
    'open',
    'resolved',
    'Under Review',
    'CivicMesh Verified',
    'Authority Verified',
  ].includes(params.get('status') ?? '')
    ? params.get('status')!
    : 'all';
  const routeParams = useParams<{ id?: string }>();
  const selectedId = params.get('issue') || routeParams.id;

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError('');
    issueService
      .list(controller.signal)
      .then(res => {
        setIssues(res.issues);
        setListMeta({ source: res.source, backendFailed: res.backendFailed });
      })
      .catch(e => {
        if (!controller.signal.aborted)
          setError(
            e instanceof Error ? e.message : 'Could not load issues. Please retry.'
          );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [attempt]);

  const filtered = issues.filter(
    i =>
      (category === 'All' || i.category === category) &&
      (status === 'all' ||
        (status === 'open' && i.status !== 'Resolved') ||
        (status === 'resolved' && i.status === 'Resolved') ||
        i.status === status) &&
      `${i.title} ${i.location} ${i.category}`
        .toLowerCase()
        .includes(query.toLowerCase().trim())
  );

  const selected = filtered.find(i => i.id === selectedId);

  useEffect(() => {
    if (selectedId)
      document.querySelector<HTMLElement>('.issue-preview h2')?.focus();
  }, [selectedId]);

  function update(key: string, value: string) {
    setParams(
      p => {
        const next = new URLSearchParams(p);
        value ? next.set(key, value) : next.delete(key);
        if (key !== 'issue') next.delete('issue');
        return next;
      },
      { replace: true }
    );
  }

  function select(id: string) {
    previousTrigger.current =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null;
    update('issue', id);
  }

  function close() {
    update('issue', '');
    requestAnimationFrame(() => {
      if (previousTrigger.current?.isConnected)
        previousTrigger.current.focus();
      else
        document.querySelector<HTMLElement>('.issue-row')?.focus();
    });
  }

  async function support(id: string) {
    const result = await issueService.toggleSupport(id);
    setIssues(items => items.map(i => (i.id === id ? result : i)));
  }

  function handleUpdate(updated: Issue) {
    setIssues(items => items.map(i => (i.id === updated.id ? updated : i)));
  }

  function clear() {
    setParams({});
  }

  return (
    <div className="map-page">
      <div className="page-heading">
        <div>
          <h1>
            Your neighborhood, <span>in focus.</span>
          </h1>
          <p>See what needs a little care. Start a change close to home.</p>
        </div>
        <Link className="primary-button heading-report" to="/report">
          <Icon name="plus" size={20} />
          Report an issue
        </Link>
      </div>

      <div className="discovery-toolbar">
        <label className="search-field">
          <Icon name="search" size={20} />
          <input
            type="search"
            aria-label="Search issues or streets"
            placeholder="Search an issue or a street…"
            value={query}
            onChange={e => update('q', e.target.value)}
          />
        </label>
        <label className="status-filter">
          <Icon name="filter" size={20} />
          <span className="sr-only">Filter by status</span>
          <select
            aria-label="Filter by status"
            value={
              [
                'all',
                'open',
                'resolved',
                'Under Review',
                'CivicMesh Verified',
                'Authority Verified',
              ].includes(status)
                ? status
                : 'all'
            }
            onChange={e => update('status', e.target.value)}
          >
            <option value="all">All statuses</option>
            <option value="open">Open issues</option>
            <option value="resolved">Resolved</option>
            <option>Under Review</option>
            <option>CivicMesh Verified</option>
            <option>Authority Verified</option>
          </select>
        </label>
        <div className="mobile-view" aria-label="View">
          <button aria-pressed={view === 'map'} onClick={() => setView('map')}>
            <Icon name="map" size={18} />
            Map
          </button>
          <button aria-pressed={view === 'list'} onClick={() => setView('list')}>
            <Icon name="list" size={18} />
            List
          </button>
        </div>
      </div>

      <div className="category-filters" aria-label="Issue categories">
        <button
          className={category === 'All' ? 'selected' : ''}
          aria-pressed={category === 'All'}
          onClick={() => update('category', '')}
        >
          All issues <span>{issues.length}</span>
        </button>
        {categories.map(c => (
          <button
            key={c}
            className={category === c ? 'selected' : ''}
            aria-pressed={category === c}
            onClick={() => update('category', c)}
          >
            <Icon name={categoryIcons[c]} size={18} />
            {c}
            <span>{issues.filter(i => i.category === c).length}</span>
          </button>
        ))}
      </div>

      <div className={`discovery-layout view-${view} ${selected ? 'has-selection' : ''}`}>
        <div className="map-column">
          <MapCanvas
            issues={filtered}
            selectedId={selected?.id ?? null}
            onSelect={select}
          />
          <div className="map-caption">
            <Icon name="people" size={17} />
            <span>Better streets start with a shared view.</span>
            {listMeta.source === 'local' && (
              <span>Sample data · Not official reports</span>
            )}
          </div>
          {listMeta.backendFailed && (
            <div
              role="status"
              style={{
                margin: '8px 12px',
                padding: '8px 12px',
                background: '#faf0e6',
                border: '1px solid #c49a6c',
                borderRadius: '6px',
                fontSize: '12px',
                color: '#684022',
              }}
            >
              Backend service was unavailable. Showing local sample data.
            </div>
          )}
        </div>

        <aside className="results-panel" aria-label="Nearby issues">
          {selected ? (
            <IssuePreview
              key={selected.id}
              issue={selected}
              onClose={close}
              onSupport={support}
              onUpdate={handleUpdate}
            />
          ) : (
            <>
              <div className="results-heading">
                <div>
                  <h2>In your neighborhood</h2>
                  <p role="status">
                    {loading
                      ? 'Loading issues…'
                      : `${filtered.length} ${
                          filtered.length === 1 ? 'issue' : 'issues'
                        } ${
                          query || category !== 'All' || status !== 'all'
                            ? 'matching your filters'
                            : 'to explore'
                        }`}
                  </p>
                </div>
                <span className="results-count">{filtered.length}</span>
              </div>

              {loading ? (
                <div className="loading-list" aria-label="Loading neighborhood issues">
                  {[0, 1, 2, 3].map(i => (
                    <div className="skeleton" key={i}>
                      <span />
                      <span />
                    </div>
                  ))}
                </div>
              ) : error ? (
                <div className="empty-state" role="alert">
                  <Icon name="refresh" size={30} />
                  <h3>Let’s try that again</h3>
                  <p>{error}</p>
                  <button
                    className="secondary-button"
                    onClick={() => setAttempt(n => n + 1)}
                  >
                    Retry issues
                  </button>
                </div>
              ) : filtered.length === 0 ? (
                <div className="empty-state">
                  <Icon name="search" size={32} />
                  <h3>No issues found</h3>
                  <p>Try another street or clear your filters to see the neighborhood.</p>
                  <button className="secondary-button" onClick={clear}>
                    Clear filters
                  </button>
                </div>
              ) : (
                <ul className="issue-list">
                  {filtered.map(issue => (
                    <li key={issue.id}>
                      <button
                        className="issue-row"
                        onClick={() => select(issue.id)}
                      >
                        <div className="issue-row-top">
                          <CategoryIcon category={issue.category} />
                          <span className="issue-category">{issue.category}</span>
                          <span className="support-count">
                            <Icon name="people" size={15} />
                            {issue.supporters}
                          </span>
                        </div>
                        <h3>{issue.title}</h3>
                        <p>
                          <Icon name="pin" size={14} />
                          {issue.location}
                        </p>
                        <div className="issue-row-bottom">
                          <StatusBadge status={issue.status} />
                          <Icon name="arrow" size={18} />
                        </div>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
              <p className="results-footnote">
                Reported by neighbors. Seen by the community.
              </p>
            </>
          )}
        </aside>
      </div>
    </div>
  );
}
