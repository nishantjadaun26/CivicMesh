import { useEffect, useRef, useState } from 'react';
import { useAuth } from '../../lib/supabase/client';
import { Icon } from '../../components/Icon';

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function AuthModal({ isOpen, onClose }: AuthModalProps) {
  const { user, isConfigured, loading, signInWithEmail, signUpWithEmail, signOut } = useAuth();
  const [isSignUp, setIsSignUp] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  const dialogRef = useRef<HTMLDivElement>(null);
  const previousActiveElement = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!isOpen) { setPassword(''); setEmail(''); setMessage(''); setError(''); }
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) return;

    // Save previous active element before modal steals focus
    previousActiveElement.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;

    // Focus the first input or modal container
    const timer = setTimeout(() => {
      if (dialogRef.current) {
        const firstFocusable = dialogRef.current.querySelector<HTMLElement>(
          'input:not([disabled]), button:not([disabled]), [tabindex]:not([tabindex="-1"])'
        );
        firstFocusable?.focus();
      }
    }, 50);

    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        e.preventDefault();
        onClose();
        return;
      }

      if (e.key === 'Tab' && dialogRef.current) {
        const focusables = dialogRef.current.querySelectorAll<HTMLElement>(
          'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'
        );
        if (focusables.length === 0) return;

        const first = focusables[0];
        const last = focusables[focusables.length - 1];

        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    }

    document.addEventListener('keydown', handleKeyDown);

    return () => {
      clearTimeout(timer);
      document.removeEventListener('keydown', handleKeyDown);
      if (previousActiveElement.current?.isConnected) {
        previousActiveElement.current.focus();
      }
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!email.trim() || !password.trim()) {
      setError('Please provide both email and password.');
      return;
    }
    setSubmitting(true);
    setError('');
    setMessage('');

    try {
      if (isSignUp) {
        const { error: err } = await signUpWithEmail(email, password);
        if (err) throw err;
        setMessage('Check your email for confirmation link or session details.');
      } else {
        const { error: err } = await signInWithEmail(email, password);
        if (err) throw err;
        setMessage('Signed in successfully.');
        setTimeout(onClose, 800);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Authentication failed.');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div
      className="modal-overlay"
      role="dialog"
      aria-modal="true"
      aria-labelledby="auth-modal-title"
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 2500,
        backgroundColor: 'rgba(40, 28, 20, 0.65)',
        backdropFilter: 'blur(3px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '16px',
      }}
      onClick={e => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        ref={dialogRef}
        className="panel auth-panel"
        style={{
          width: '100%',
          maxWidth: '420px',
          margin: 0,
          background: 'var(--surface)',
          borderRadius: '16px',
          boxShadow: '0 20px 48px rgba(0,0,0,0.22)',
          position: 'relative',
        }}
      >
        <button
          type="button"
          onClick={onClose}
          aria-label="Close modal"
          style={{
            position: 'absolute',
            top: '16px',
            right: '16px',
            background: 'none',
            border: 0,
            cursor: 'pointer',
            color: 'var(--muted)',
            padding: '4px',
          }}
        >
          <Icon name="close" size={20} />
        </button>

        <h2 id="auth-modal-title" style={{ fontSize: '22px', marginBottom: '8px' }}>
          {user ? 'Citizen Account' : isSignUp ? 'Join CivicMesh' : 'Citizen Sign In'}
        </h2>
        <p style={{ fontSize: '13px', color: 'var(--muted)', marginBottom: '20px' }}>
          {user
            ? `Signed in as ${user.email}`
            : 'Access your submitted reports, track campaign updates, and verify community outcomes.'}
        </p>

        {!isConfigured ? (
          <div
            style={{
              padding: '16px',
              backgroundColor: '#faf2e6',
              border: '1.5px dashed #c49a6c',
              borderRadius: '10px',
              marginBottom: '16px',
            }}
          >
            <strong style={{ display: 'block', fontSize: '13px', color: '#684022', marginBottom: '6px' }}>
              Authentication is not configured
            </strong>
            <p style={{ fontSize: '12px', color: 'var(--muted)', lineHeight: '1.6', margin: 0 }}>
              Set <code>VITE_SUPABASE_URL</code> and <code>VITE_SUPABASE_ANON_KEY</code> in your environment to
              connect live Supabase Auth. Private actions require configured services and sign-in.
            </p>
          </div>
        ) : user ? (
          <div>
            <div style={{ padding: '14px', background: 'var(--ground)', borderRadius: '8px', marginBottom: '16px' }}>
              <div style={{ fontSize: '12px', color: 'var(--muted)' }}>User ID</div>
              <div style={{ fontSize: '13px', fontFamily: 'monospace', wordBreak: 'break-all' }}>{user.id}</div>
              <div style={{ fontSize: '12px', color: 'var(--muted)', marginTop: '8px' }}>Email</div>
              <div style={{ fontSize: '14px', fontWeight: 700 }}>{user.email}</div>
            </div>
            <button
              type="button"
              className="primary-button"
              style={{ width: '100%' }}
              onClick={async () => {
                try { await signOut(); onClose(); }
                catch (error) { setError(error instanceof Error ? error.message : 'Sign-out could not complete.'); }
              }}
            >
              Sign out
            </button>
            {error && <p role="alert">{error}</p>}
          </div>
        ) : (
          <form onSubmit={handleSubmit}>
            <label style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginBottom: '14px' }}>
              <span style={{ fontSize: '13px', fontWeight: 700 }}>Email address</span>
              <input
                type="email"
                required
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="citizen@example.org"
                style={{
                  height: '44px',
                  padding: '0 12px',
                  borderRadius: '8px',
                  border: '1px solid var(--edge)',
                  background: 'var(--surface)',
                }}
              />
            </label>

            <label style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginBottom: '18px' }}>
              <span style={{ fontSize: '13px', fontWeight: 700 }}>Password</span>
              <input
                type="password"
                required
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="••••••••"
                style={{
                  height: '44px',
                  padding: '0 12px',
                  borderRadius: '8px',
                  border: '1px solid var(--edge)',
                  background: 'var(--surface)',
                }}
              />
            </label>

            {error && (
              <p role="alert" className="error-text" style={{ marginBottom: '14px' }}>
                {error}
              </p>
            )}

            {message && (
              <p role="status" style={{ color: 'var(--green)', fontSize: '13px', marginBottom: '14px' }}>
                {message}
              </p>
            )}

            <button
              type="submit"
              className="primary-button"
              disabled={submitting || loading}
              style={{ width: '100%', minHeight: '44px', marginBottom: '12px' }}
            >
              {submitting ? 'Please wait…' : isSignUp ? 'Create account' : 'Sign in'}
            </button>

            <button
              type="button"
              className="text-button"
              style={{ width: '100%', justifyContent: 'center' }}
              onClick={() => {
                setIsSignUp(prev => !prev);
                setError('');
                setMessage('');
              }}
            >
              {isSignUp ? 'Already have an account? Sign in' : "Don't have an account? Sign up"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
