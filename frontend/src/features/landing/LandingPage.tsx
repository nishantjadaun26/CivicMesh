import { useEffect, useState, useRef, useCallback } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import '../../styles/landing.css';

export function LandingPage() {
  const navigate = useNavigate();
  const [isPaused, setIsPaused] = useState(false);
  const [isTabHidden, setIsTabHidden] = useState(false);

  const stageRef = useRef<HTMLDivElement>(null);
  const skyRef = useRef<HTMLDivElement>(null);
  const midRef = useRef<HTMLDivElement>(null);
  const foreRef = useRef<HTMLDivElement>(null);
  const rafId = useRef<number | null>(null);

  // Respect system prefers-reduced-motion
  useEffect(() => {
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    if (mq.matches) setIsPaused(true);

    const onMqChange = (e: MediaQueryListEvent) => {
      if (e.matches) setIsPaused(true);
    };
    mq.addEventListener('change', onMqChange);
    return () => mq.removeEventListener('change', onMqChange);
  }, []);

  // Pause animations when browser tab is hidden to conserve GPU & battery
  useEffect(() => {
    const handleVisibility = () => {
      setIsTabHidden(document.hidden);
    };
    document.addEventListener('visibilitychange', handleVisibility);
    return () => document.removeEventListener('visibilitychange', handleVisibility);
  }, []);

  // Subtle environmental parallax between foreground, midground and background
  // Follows Emil Kowalski's performance rule: write to ref.current.style, avoid state re-renders
  const handleMouseMove = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    if (isPaused || isTabHidden) return;
    if (!stageRef.current) return;

    if (rafId.current) cancelAnimationFrame(rafId.current);

    rafId.current = requestAnimationFrame(() => {
      if (!stageRef.current) return;
      const rect = stageRef.current.getBoundingClientRect();
      const nx = ((e.clientX - rect.left) / rect.width - 0.5) * 2; // -1 to 1
      const ny = ((e.clientY - rect.top) / rect.height - 0.5) * 2; // -1 to 1

      // Subtle parallax displacements (pixels)
      if (skyRef.current) {
        skyRef.current.style.transform = `translate3d(${-nx * 1.5}px, ${-ny * 1}px, 0)`;
      }
      if (midRef.current) {
        midRef.current.style.transform = `translate3d(${nx * 2}px, ${ny * 1.5}px, 0)`;
      }
      if (foreRef.current) {
        foreRef.current.style.transform = `translate3d(${nx * 4}px, ${ny * 3}px, 0)`;
      }
    });
  }, [isPaused, isTabHidden]);

  const handleMouseLeave = useCallback(() => {
    if (rafId.current) cancelAnimationFrame(rafId.current);
    if (skyRef.current) skyRef.current.style.transform = 'translate3d(0, 0, 0)';
    if (midRef.current) midRef.current.style.transform = 'translate3d(0, 0, 0)';
    if (foreRef.current) foreRef.current.style.transform = 'translate3d(0, 0, 0)';
  }, []);

  const togglePause = useCallback(() => {
    setIsPaused(prev => !prev);
  }, []);

  // Keyboard shortcut: Space toggles animation pause
  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.code === 'Space' && (e.target as HTMLElement).tagName !== 'BUTTON') {
      e.preventDefault();
      togglePause();
    }
  }, [togglePause]);

  const pausedClass = (isPaused || isTabHidden) ? 'animations-paused' : '';

  return (
    <div
      className={`landing-viewport ${pausedClass}`}
      onKeyDown={handleKeyDown}
      tabIndex={0}
      role="region"
      aria-label="CivicMesh animated landing page"
    >
      <div
        ref={stageRef}
        className="landing-stage"
        onMouseMove={handleMouseMove}
        onMouseLeave={handleMouseLeave}
      >
        {/* =========================================================
            SCENE: Living 2D Animated Environment
            ========================================================= */}
        <div className="landing-scene" aria-hidden="true">
          {/* Depth Plane 0: Background & Drifting Clouds */}
          <div ref={skyRef} className="scene-plane sky-plane">
            {/* Master authentic approved city illustration */}
            <img
              src="/landing/landing-illustration.png"
              alt=""
              className="base-illustration"
              loading="eager"
            />

            {/* 1. Clouds drifting slowly across upper sky */}
            <div className="clouds-track">
              <img
                src="/landing/cloud-1.png"
                alt=""
                className="cloud cloud-top"
              />
              <img
                src="/landing/cloud-2.png"
                alt=""
                className="cloud cloud-mid"
              />
            </div>
          </div>

          {/* Depth Plane 1: Midground Lighting, Bus, Glowing Windows */}
          <div ref={midRef} className="scene-plane mid-plane">
            {/* 4. Streetlights and shop windows softly glowing */}
            <div className="lighting-plane">
              {/* Streetlamp primary lantern glow */}
              <div className="streetlamp-lantern-glow" />
              {/* Distant streetlamp glow */}
              <div className="distant-lantern-glow" />
              {/* Café window warm interior light */}
              <div className="cafe-interior-glow" />
              {/* Market shopfront warm ambient light */}
              <div className="market-shop-glow" />
              {/* Upstairs apartment window warm light */}
              <div className="upstairs-room-glow" />
            </div>

            {/* 5. Bus moving slowly along the street with headlight effects */}
            <div className="bus-motion-plane">
              <div className="bus-bob-wrap">
                <img
                  src="/landing/bus.png"
                  alt=""
                  className="bus-sprite-img"
                />
                {/* Volumetric headlight beam cone */}
                <div className="headlight-cone" />
              </div>
            </div>
            {/* Road specular light reflection */}
            <div className="asphalt-headlight-specular" />
          </div>

          {/* Depth Plane 2: Foreground Swaying Tree Canopy, Shimmering Puddle, Falling Leaves */}
          <div ref={foreRef} className="scene-plane fore-plane">
            {/* 2. Tree branches and leaves gently swaying */}
            <div className="tree-sway-plane">
              <img
                src="/landing/tree-canopy.png"
                alt=""
                className="tree-canopy-sprite"
              />
            </div>

            {/* 6. Puddle reflections gently shimmering */}
            <div className="puddle-shimmer-plane">
              <svg
                className="puddle-svg"
                viewBox="0 0 399 200"
                preserveAspectRatio="none"
              >
                <defs>
                  <linearGradient id="puddleWaterGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#ffe49e" stopOpacity="0.75" />
                    <stop offset="45%" stopColor="#ffb03a" stopOpacity="0.45" />
                    <stop offset="100%" stopColor="#f58826" stopOpacity="0.1" />
                  </linearGradient>
                  <linearGradient id="puddleGlintGrad" x1="0" y1="0" x2="1" y2="0">
                    <stop offset="0%" stopColor="#ffffff" stopOpacity="0.2" />
                    <stop offset="50%" stopColor="#ffffff" stopOpacity="0.75" />
                    <stop offset="100%" stopColor="#ffffff" stopOpacity="0.2" />
                  </linearGradient>
                </defs>
                {/* Gentle ripple waves */}
                <path
                  className="water-shimmer-wave"
                  d="M60 90 Q120 75 190 88 T320 85 Q260 115 170 110 T60 90 Z"
                  fill="url(#puddleWaterGrad)"
                />
                <path
                  className="water-shimmer-wave-alt"
                  d="M100 115 Q160 102 230 112 T350 110 Q280 135 180 130 T100 115 Z"
                  fill="url(#puddleWaterGrad)"
                />
                {/* Specular highlights */}
                <ellipse
                  className="water-shimmer-wave"
                  cx="180"
                  cy="98"
                  rx="65"
                  ry="5"
                  fill="url(#puddleGlintGrad)"
                />
                <ellipse
                  className="water-shimmer-wave-alt"
                  cx="240"
                  cy="120"
                  rx="48"
                  ry="4"
                  fill="url(#puddleGlintGrad)"
                />
              </svg>
            </div>

            {/* 3. A few leaves falling occasionally */}
            <div className="falling-leaves-container">
              {/* Leaf A */}
              <div className="falling-leaf leaf-a">
                <svg viewBox="0 0 24 24" fill="#e8772a" width="100%" height="100%">
                  <path d="M12 2 C8 6 3 10 4 16 C5 21 11 22 14 18 C17 14 20 8 12 2 Z" />
                  <path d="M12 4 L11 18" stroke="#aa4d15" strokeWidth="1" />
                </svg>
              </div>
              {/* Leaf B */}
              <div className="falling-leaf leaf-b">
                <svg viewBox="0 0 24 24" fill="#ea9c3a" width="100%" height="100%">
                  <path d="M4 14 C8 10 14 4 20 6 C22 12 18 18 12 19 C7 20 3 18 4 14 Z" />
                  <path d="M6 13 L17 8" stroke="#ba681b" strokeWidth="1" />
                </svg>
              </div>
              {/* Leaf C */}
              <div className="falling-leaf leaf-c">
                <svg viewBox="0 0 24 24" fill="#d9581a" width="100%" height="100%">
                  <path d="M10 2 C16 4 20 10 18 16 C16 20 10 22 6 18 C3 14 6 6 10 2 Z" />
                  <path d="M10 4 L8 18" stroke="#96350c" strokeWidth="1" />
                </svg>
              </div>
            </div>
          </div>
        </div>

        {/* =========================================================
            UI & INTERACTION LAYER
            ========================================================= */}
        {/* Top Header: Brand Link & Pause/Resume Control */}
        <header className="landing-top-bar">
          <Link
            to="/map"
            className="top-brand-link"
            aria-label="CivicMesh — Return to neighborhood map"
          >
            <span className="sr-only">CivicMesh</span>
          </Link>

          <button
            type="button"
            className="pause-toggle-button"
            onClick={togglePause}
            aria-label={isPaused ? "Resume animations" : "Pause animations"}
            title={isPaused ? "Resume animations (Space)" : "Pause animations (Space)"}
          >
            <svg
              className="toggle-icon"
              viewBox="0 0 24 24"
              fill="currentColor"
              aria-hidden="true"
            >
              {isPaused ? (
                <path d="M6 4l15 8-15 8V4z" />
              ) : (
                <path d="M6 4h4v16H6V4zm8 0h4v16h-4V4z" />
              )}
            </svg>
            <span>{isPaused ? "Resume" : "Pause"}</span>
          </button>
        </header>

        {/* Accessible hidden text for screen readers */}
        <h1 className="sr-only">Your City Deserves to Be Heard.</h1>
        <p className="sr-only">
          Report local problems, discover nearby issues, and bring your community together.
        </p>

        {/* Bottom Navigation Interactive Hotspots */}
        <nav className="bottom-nav-overlay" aria-label="Landing navigation">
          <button
            type="button"
            className="nav-hitbox"
            onClick={() => navigate('/map')}
            aria-label="Neighborhood map"
          >
            <span className="sr-only">Map</span>
          </button>

          <button
            type="button"
            className="nav-hitbox"
            onClick={() => navigate('/report')}
            aria-label="Report an issue"
          >
            <span className="sr-only">Report</span>
          </button>

          <button
            type="button"
            className="nav-hitbox"
            onClick={() => navigate('/campaigns')}
            aria-label="Community campaigns"
          >
            <span className="sr-only">Campaigns</span>
          </button>
        </nav>
      </div>
    </div>
  );
}
