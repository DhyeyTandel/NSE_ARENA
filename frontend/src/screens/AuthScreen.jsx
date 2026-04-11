// screens/AuthScreen.jsx
import { useState } from 'react';
import './AuthScreen.css';

export function AuthScreen({ onAuth, error, clearError }) {
  const [mode, setMode] = useState('login');  // 'login' or 'register'
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
    if (username.length < 3) {
      setValidationError('Username must be at least 3 characters');
      return false;
    }
    if (password.length < 6) {
      setValidationError('Password must be at least 6 characters');
      return false;
    }
    if (mode === 'register') {
      if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
        setValidationError('Please enter a valid email address');
        return false;
      }
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
      <div className="auth-card">
        {/* Logo */}
        <div className="auth-logo">
          nse<span className="gold">arena</span>
        </div>
        <div className="auth-subtitle">
          Paper trading competition for Indian markets
        </div>

        {/* Login / Register tabs */}
        <div className="auth-tabs">
          <button
            className={`auth-tab ${mode === 'login' ? 'active' : ''}`}
            onClick={() => switchMode('login')}
            type="button"
          >
            Login
          </button>
          <button
            className={`auth-tab ${mode === 'register' ? 'active' : ''}`}
            onClick={() => switchMode('register')}
            type="button"
          >
            Register
          </button>
        </div>

        {/* Error */}
        {displayError && (
          <div className="auth-error">{displayError}</div>
        )}

        {/* Form */}
        <form className="auth-form" onSubmit={handleSubmit}>
          <div className="auth-field">
            <label htmlFor="auth-username">Username</label>
            <input
              id="auth-username"
              type="text"
              value={username}
              onChange={e => setUsername(e.target.value)}
              placeholder="e.g. SharpeEdge"
              autoComplete="username"
              autoFocus
            />
          </div>

          {mode === 'register' && (
            <div className="auth-field">
              <label htmlFor="auth-email">Email</label>
              <input
                id="auth-email"
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="you@example.com"
                autoComplete="email"
              />
            </div>
          )}

          <div className="auth-field">
            <label htmlFor="auth-password">Password</label>
            <input
              id="auth-password"
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="••••••••"
              autoComplete={mode === 'register' ? 'new-password' : 'current-password'}
            />
          </div>

          <button
            type="submit"
            className={`auth-submit ${submitting ? 'loading' : ''}`}
            disabled={submitting}
          >
            {mode === 'login' ? 'Sign In' : 'Create Account'}
          </button>
        </form>

        {/* Footer */}
        <div className="auth-footer">
          Start with <span>₹1,00,000</span> virtual capital · Compete in seasonal leaderboards
        </div>
      </div>
    </div>
  );
}
