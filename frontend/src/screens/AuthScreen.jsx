// screens/AuthScreen.jsx
import { useState } from 'react';
import { ThemeToggle } from '../components/ThemeToggle';
import './AuthScreen.css';

export function AuthScreen({ onAuth, error, clearError }) {
  const [mode, setMode] = useState('login');
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [validationError, setValidationError] = useState('');

  const switchMode = (newMode) => {
    setMode(newMode);
    setValidationError('');
    if (clearError) clearError();
  };

  const validate = () => {
    if (mode === 'register') {
      if (!/^[A-Za-z0-9_-]{3,30}$/.test(username)) {
        setValidationError('Username must be 3-30 characters: letters, numbers, _ or -');
        return false;
      }
      if (!email || email.length > 100 || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
        setValidationError('Please enter a valid email address');
        return false;
      }
      if (password.length < 8 || password.length > 128) {
        setValidationError('Password must be 8-128 characters');
        return false;
      }
    } else if (!username || !password) {
      // Login: no length rules, accounts predate the registration limits.
      setValidationError('Enter your username and password');
      return false;
    }
    setValidationError('');
    return true;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!validate()) return;

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

  const displayError = validationError || error;

  return (
    <div className="auth-container">
      <div className="auth-theme"><ThemeToggle /></div>
      <div className="auth-card">
        <div className="auth-logo">
          <span className="nav-mark" aria-hidden="true">N</span>
          NSE Arena
        </div>
        <div className="auth-subtitle">
          Master the markets. Zero real risk.
        </div>

        <div className="seg seg--block" role="tablist">
          <button type="button" role="tab" aria-selected={mode === 'login'}
            className={mode === 'login' ? 'is-active' : ''} onClick={() => switchMode('login')}>
            Sign in
          </button>
          <button type="button" role="tab" aria-selected={mode === 'register'}
            className={mode === 'register' ? 'is-active' : ''} onClick={() => switchMode('register')}>
            Create account
          </button>
        </div>

        {displayError && (
          <div className="auth-error" role="alert">{displayError}</div>
        )}

        {/* Form */}
        <form className="auth-form" onSubmit={handleSubmit}>
          <div className="auth-field">
            <label htmlFor="auth-username">Username</label>
            <input
              className="input"
              id="auth-username"
              type="text"
              value={username}
              onChange={e => setUsername(e.target.value)}
              placeholder="your_trader_name"
              minLength={mode === 'register' ? 3 : undefined}
              maxLength={mode === 'register' ? 30 : undefined}
              autoComplete="username"
              autoFocus
            />
          </div>

          {mode === 'register' && (
            <div className="auth-field">
              <label htmlFor="auth-email">Email</label>
              <input
              className="input"
                id="auth-email"
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="you@example.com"
                maxLength={100}
                autoComplete="email"
              />
            </div>
          )}

          <div className="auth-field">
            <label htmlFor="auth-password">Password</label>
            <input
              className="input"
              id="auth-password"
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder={mode === 'register' ? 'At least 8 characters' : '••••••••'}
              minLength={mode === 'register' ? 8 : undefined}
              maxLength={mode === 'register' ? 128 : undefined}
              autoComplete={mode === 'register' ? 'new-password' : 'current-password'}
            />
          </div>

          <button
            type="submit"
            className={`btn btn--block auth-submit ${submitting ? 'loading' : ''}`}
            disabled={submitting}
          >
            {mode === 'login' ? 'Sign in' : 'Create account'}
          </button>
        </form>

        <div className="auth-footer">
          ₹1,00,000 virtual capital · Live NSE data · AI competitors · Seasonal leagues
        </div>
      </div>
    </div>
  );
}
