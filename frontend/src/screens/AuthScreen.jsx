// screens/AuthScreen.jsx
import { useState } from 'react';
import { ThemeToggle } from '../components/ThemeToggle';
import { Logo } from '../components/Logo';
import './AuthScreen.css';

const FEATURES = [
  {
    title: '₹1,00,000 virtual capital',
    text: 'Start every season with the same stake. No real money is ever at risk.',
    icon: <path d="M6 5h12M6 9h12M9 5c4 0 6 2 6 4s-2 4-6 4h-1l7 6" />,
  },
  {
    title: 'Live NSE prices',
    text: 'Trade against the NSE price feed and watch the market move as it happens.',
    icon: <path d="M3 17l5-5 4 4 8-9M15 7h5v5" />,
  },
  {
    title: 'AI competitors and seasons',
    text: 'AI agents trade alongside you, and every season ends with a ranked leaderboard.',
    icon: <path d="M8 21h8M12 17v4M7 4h10v4a5 5 0 0 1-10 0V4zM7 6H4v1a3 3 0 0 0 3 3M17 6h3v1a3 3 0 0 1-3 3" />,
  },
];

const USERNAME_RE = /^[A-Za-z0-9_-]{3,30}$/;
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function fieldErrors(mode, { username, email, password }) {
  const errs = {};
  if (mode === 'register') {
    if (!USERNAME_RE.test(username)) errs.username = 'Use 3 to 30 characters: letters, numbers, _ or -';
    if (!email || email.length > 100 || !EMAIL_RE.test(email)) errs.email = 'Enter a valid email address';
    if (password.length < 8 || password.length > 128) errs.password = 'Use 8 to 128 characters';
  } else {
    // Login: no length rules, accounts predate the registration limits.
    if (!username) errs.username = 'Enter your username';
    if (!password) errs.password = 'Enter your password';
  }
  return errs;
}

export function AuthScreen({ onAuth, error, clearError }) {
  const [mode, setMode] = useState('login');
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPw, setShowPw] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [touched, setTouched] = useState({});
  const [attempted, setAttempted] = useState(false);

  const errs = fieldErrors(mode, { username, email, password });
  const shown = key => ((touched[key] || attempted) && errs[key]) || '';
  const touch = key => setTouched(t => ({ ...t, [key]: true }));

  const switchMode = (newMode) => {
    setMode(newMode);
    setTouched({});
    setAttempted(false);
    if (clearError) clearError();
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setAttempted(true);
    if (Object.keys(errs).length > 0) return;

    setSubmitting(true);
    try {
      if (mode === 'login') {
        await onAuth('login', { username, password });
      } else {
        await onAuth('register', { username, email, password });
      }
    } finally {
      setSubmitting(false);
    }
  };

  const field = (key, label, input) => (
    <div className="auth-field">
      <label htmlFor={`auth-${key}`}>{label}</label>
      {input}
      {shown(key) && <div className="auth-field-error" id={`auth-${key}-err`}>{shown(key)}</div>}
    </div>
  );
  const aria = key => ({
    'aria-invalid': shown(key) ? 'true' : undefined,
    'aria-describedby': shown(key) ? `auth-${key}-err` : undefined,
    onBlur: () => touch(key),
  });

  const isLogin = mode === 'login';

  return (
    <div className="auth">
      <aside className="auth-brand">
        <Logo size={36} variant="full" className="auth-brand-logo" />
        <div className="auth-brand-body">
          <h1 className="auth-tagline">Master the markets. Zero real risk.</h1>
          <ul className="auth-features">
            {FEATURES.map(f => (
              <li key={f.title}>
                <span className="auth-feature-icon" aria-hidden="true">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">{f.icon}</svg>
                </span>
                <div>
                  <div className="auth-feature-title">{f.title}</div>
                  <div className="auth-feature-text">{f.text}</div>
                </div>
              </li>
            ))}
          </ul>
        </div>
      </aside>

      <main className="auth-main">
        <div className="auth-theme"><ThemeToggle /></div>
        <div className="auth-card">
          <Logo size={28} variant="full" className="auth-card-logo" />
          <h2 className="auth-title">{isLogin ? 'Welcome back' : 'Create your account'}</h2>
          <p className="auth-subtitle">
            {isLogin ? 'Sign in to continue trading.' : 'Free to join. Start with ₹1,00,000 in virtual cash.'}
          </p>

          <div className="seg seg--block" role="tablist" aria-label="Account">
            <button type="button" role="tab" aria-selected={isLogin}
              className={isLogin ? 'is-active' : ''} onClick={() => switchMode('login')}>
              Sign in
            </button>
            <button type="button" role="tab" aria-selected={!isLogin}
              className={!isLogin ? 'is-active' : ''} onClick={() => switchMode('register')}>
              Create account
            </button>
          </div>

          {error && <div className="auth-error" role="alert">{error}</div>}

          <form className="auth-form" onSubmit={handleSubmit} noValidate>
            {field('username', 'Username',
              <input
                className="input" id="auth-username" type="text" value={username}
                onChange={e => setUsername(e.target.value)} placeholder="your_trader_name"
                maxLength={isLogin ? undefined : 30}
                autoComplete="username" autoFocus {...aria('username')}
              />)}

            {!isLogin && field('email', 'Email',
              <input
                className="input" id="auth-email" type="email" value={email}
                onChange={e => setEmail(e.target.value)} placeholder="you@example.com"
                maxLength={100} autoComplete="email" {...aria('email')}
              />)}

            {field('password', 'Password',
              <div className="auth-pw">
                <input
                  className="input" id="auth-password" type={showPw ? 'text' : 'password'} value={password}
                  onChange={e => setPassword(e.target.value)}
                  placeholder={isLogin ? 'Your password' : 'At least 8 characters'}
                  maxLength={isLogin ? undefined : 128}
                  autoComplete={isLogin ? 'current-password' : 'new-password'} {...aria('password')}
                />
                <button type="button" className="auth-pw-toggle" aria-pressed={showPw}
                  onClick={() => setShowPw(v => !v)}>
                  {showPw ? 'Hide' : 'Show'}
                </button>
              </div>)}

            <button type="submit" className={`btn btn--lg btn--block auth-submit${submitting ? ' is-loading' : ''}`} disabled={submitting}>
              {submitting && <span className="spinner" aria-hidden="true" />}
              {submitting ? (isLogin ? 'Signing in' : 'Creating account') : (isLogin ? 'Sign in' : 'Create account')}
            </button>
          </form>

          <p className="auth-switch">
            {isLogin ? 'New to NSE Arena?' : 'Already have an account?'}{' '}
            <button type="button" className="link-btn" onClick={() => switchMode(isLogin ? 'register' : 'login')}>
              {isLogin ? 'Create an account' : 'Sign in'}
            </button>
          </p>
        </div>
      </main>
    </div>
  );
}
