// components/NavBar.jsx
import { useState, useEffect, useRef } from 'react';
import { useSeasonStanding } from '../hooks/useSeasonStanding';
import { ThemeToggle } from './ThemeToggle';
import { Logo } from './Logo';
import './NavBar.css';

const NAV_ITEMS = [
  { key: 'dashboard', label: 'Dashboard' },
  { key: 'leaderboard', label: 'Leaderboard' },
  { key: 'scripts', label: 'Scripts' },
  { key: 'ai-feed', label: 'AI agents' },
];

export function NavBar({ activeScreen, onNavigate, user, onLogout }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef(null);
  const standing = useSeasonStanding(!!user, user);

  useEffect(() => {
    if (!menuOpen) return undefined;
    const onDown = (e) => { if (menuRef.current && !menuRef.current.contains(e.target)) setMenuOpen(false); };
    const onKey = (e) => { if (e.key === 'Escape') setMenuOpen(false); };
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [menuOpen]);

  const seasonParts = [];
  if (standing.season) {
    seasonParts.push(standing.season.name);
    if (standing.daysLeft != null) {
      seasonParts.push(`${standing.daysLeft} ${standing.daysLeft === 1 ? 'day' : 'days'} left`);
    }
    if (standing.rank != null) {
      seasonParts.push(`Rank #${standing.rank}${standing.traderCount > 0 ? ` of ${standing.traderCount.toLocaleString('en-IN')}` : ''}`);
    }
  } else if (!standing.loading) {
    seasonParts.push('No active season');
  }

  return (
    <nav className="nav" aria-label="Main">
      <button type="button" className="nav-logo" aria-label="NSE Arena home" onClick={() => onNavigate('dashboard')}>
        <Logo size={28} variant="full" />
      </button>

      <div className="nav-links">
        {NAV_ITEMS.map(item => (
          <button
            key={item.key} type="button"
            className={`nav-link${activeScreen === item.key ? ' is-active' : ''}`}
            aria-current={activeScreen === item.key ? 'page' : undefined}
            onClick={() => onNavigate(item.key)}
          >
            {item.label}
          </button>
        ))}
      </div>

      <div className="nav-right">
        {seasonParts.length > 0 && (
          <div className="nav-season" data-testid="season-line" title={seasonParts.join(' · ')}>{seasonParts.join(' · ')}</div>
        )}
        <div className="nav-tools">
          <ThemeToggle />
          <div className="nav-user" ref={menuRef}>
            <button
              type="button"
              className={`nav-avatar${activeScreen === 'profile' ? ' is-active' : ''}`}
              aria-label="Account menu" aria-haspopup="menu" aria-expanded={menuOpen}
              onClick={() => setMenuOpen(o => !o)}
            >
              {user?.initials || '??'}
            </button>
            {menuOpen && (
              <div className="nav-menu" role="menu">
                <div className="nav-menu-head">
                  <div className="nav-menu-name">{user?.username}</div>
                  {user?.email && <div className="nav-menu-email">{user.email}</div>}
                </div>
                <button type="button" role="menuitem" onClick={() => { setMenuOpen(false); onNavigate('profile'); }}>
                  Profile
                </button>
                {onLogout && (
                  <button type="button" role="menuitem" className="nav-menu-out" onClick={() => { setMenuOpen(false); onLogout(); }}>
                    Sign out
                  </button>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </nav>
  );
}
