import { useEffect, useRef } from 'react';
import { NavLink, Navigate, Route, Routes, useLocation, Link } from 'react-router-dom';
import { Icon } from '../components/Icon';
import { ReportPage } from '../features/reports/ReportPage';
import { CampaignsPage } from '../features/campaigns/CampaignsPage';
import { ProfilePage } from '../features/profile/ProfilePage';
import { MapPage } from '../features/incidents/MapPage';

const destinations = [
  { to: '/map', label: 'Map', icon: 'map' },
  { to: '/report', label: 'Report', icon: 'plus' },
  { to: '/campaigns', label: 'Campaigns', icon: 'people' },
] as const;

export function App() {
  const location = useLocation();
  const main = useRef<HTMLElement>(null);
  const first = useRef(true);

  useEffect(() => {
    document.title = `CivicMesh — ${
      location.pathname === '/map'
        ? 'Neighborhood map'
        : location.pathname === '/report'
        ? 'Report an issue'
        : location.pathname.startsWith('/campaigns')
        ? 'Campaigns'
        : location.pathname === '/profile'
        ? 'Profile'
        : 'CivicMesh'
    }`;
    if (first.current) {
      first.current = false;
      return;
    }
    main.current?.focus();
  }, [location.pathname]);

  // Fully responsive citizen application shell for all screen sizes (desktop, tablet, mobile)
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <aside className="sidebar">
        <Link className="brand" to="/map" aria-label="CivicMesh home">
          Civic<span>Mesh</span>
          <svg viewBox="0 0 100 10" aria-hidden="true">
            <path d="M2 6Q45 1 96 5M7 8Q56 4 90 7" />
          </svg>
        </Link>
        <p className="brand-caption">Small actions. Better streets.</p>
        <nav aria-label="Primary navigation">
          {destinations.map(item => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `nav-link ${item.icon === 'plus' ? 'report-nav' : ''} ${
                  isActive ? 'active' : ''
                }`
              }
            >
              <span className="nav-icon">
                <Icon name={item.icon} />
              </span>
              <span>{item.label}</span>
              {item.icon === 'map' && (
                <span className="nav-dot" aria-hidden="true" />
              )}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-note">
          <Icon name="pin" size={24} />
          <p>
            A little care goes
            <br />a long way.
          </p>
          <span>Made for your neighborhood.</span>
        </div>
        <span className="sidebar-footer">CivicMesh · Citizen prototype</span>
      </aside>

      <div className="workspace">
        <header className="topbar">
          <Link className="mobile-brand" to="/map">
            Civic<span>Mesh</span>
          </Link>
          <div className="location-label">
            <Icon name="pin" size={18} />
            <span>Pilot locality: not configured</span>
          </div>
          <div className="header-right">
            <span className="demo-label">Citizen workspace</span>
            <Link to="/profile" className="avatar" aria-label="Open profile">
              ?
            </Link>
          </div>
        </header>

        <main ref={main} id="main" tabIndex={-1}>
          <Routes>
            <Route path="/" element={<Navigate to="/map" replace />} />
            <Route path="/map" element={<MapPage />} />
            <Route path="/incidents" element={<MapPage />} />
            <Route path="/incidents/:id" element={<MapPage />} />
            <Route path="/report" element={<ReportPage />} />
            <Route path="/campaigns" element={<CampaignsPage />} />
            <Route path="/campaigns/:id" element={<CampaignsPage />} />
            <Route path="/profile" element={<ProfilePage />} />
            <Route path="*" element={<Navigate to="/map" replace />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}
