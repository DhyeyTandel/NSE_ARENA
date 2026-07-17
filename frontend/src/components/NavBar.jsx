// components/NavBar.jsx
import { useState, useEffect } from 'react';

const NAV_ITEMS = [
  {
    key: 'dashboard',
    label: 'Dashboard',
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <rect x="3" y="3" width="7" height="9" rx="1"/>
        <rect x="14" y="3" width="7" height="5" rx="1"/>
        <rect x="14" y="12" width="7" height="9" rx="1"/>
        <rect x="3" y="16" width="7" height="5" rx="1"/>
      </svg>
    ),
  },
  {
    key: 'leaderboard',
    label: 'Leaderboard',
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M6 9H4.5a2 2 0 0 1 0-4H6"/>
        <path d="M18 9h1.5a2 2 0 0 0 0-4H18"/>
        <path d="M4 22h16"/>
        <path d="M10 14.66V17c0 .55-.47.98-.97 1.21C7.85 18.75 7 20 7 22"/>
        <path d="M14 14.66V17c0 .55.47.98.97 1.21C16.15 18.75 17 20 17 22"/>
        <path d="M18 2H6v7a6 6 0 0 0 12 0V2Z"/>
      </svg>
    ),
  },
  {
    key: 'ai-feed',
    label: 'AI Insights',
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 8V4H8"/>
        <rect width="16" height="12" x="4" y="8" rx="2"/>
        <path d="M2 14h2"/>
        <path d="M20 14h2"/>
        <path d="M15 13v2"/>
        <path d="M9 13v2"/>
      </svg>
    ),
  },
  {
    key: 'scripts',
    label: 'Pine Editor',
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <polyline points="16 18 22 12 16 6"/>
        <polyline points="8 6 2 12 8 18"/>
        <line x1="14" y1="4" x2="10" y2="20"/>
      </svg>
    ),
  },
  {
    key: 'profile',
    label: 'Profile',
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="8" r="5"/>
        <path d="M20 21a8 8 0 1 0-16 0"/>
      </svg>
    ),
  },
];

export function NavBar({ activeScreen, onNavigate, user, onLogout }) {
  const [season, setSeason] = useState(null);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const fetchSeason = async () => {
      try {
        const response = await fetch('http://localhost:8000/seasons/active');
        if (response.ok) {
          const data = await response.json();
          if (data) setSeason(data);
        }
      } catch {
        // Use fallback
      }
    };
    fetchSeason();
  }, []);

  useEffect(() => {
    const handleScroll = () => setScrolled(window.scrollY > 8);
    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  const seasonLabel = season
    ? `${season.name.replace('Season ', 'S')} · ${season.days_remaining}d`
    : 'S1 · —';

  return (
    <nav style={{
      position: 'sticky',
      top: 0,
      zIndex: 100,
      height: '56px',
      background: scrolled ? 'rgba(244,240,233,0.85)' : 'var(--paper)',
      backdropFilter: scrolled ? 'blur(16px) saturate(1.2)' : 'none',
      WebkitBackdropFilter: scrolled ? 'blur(16px) saturate(1.2)' : 'none',
      borderBottom: `1px solid ${scrolled ? 'var(--faint)' : 'var(--faint)'}`,
      display: 'flex',
      alignItems: 'center',
      padding: '0 24px',
      transition: `all var(--dur) var(--ease-swift)`,
    }}>
      {/* Logo */}
      <div
        style={{
          display: 'flex', alignItems: 'center', gap: '8px',
          marginRight: '36px', cursor: 'pointer',
        }}
        onClick={() => onNavigate('dashboard')}
      >
        <div style={{
          width: '28px', height: '28px', borderRadius: 'var(--r-input)',
          background: 'linear-gradient(135deg, var(--accent) 0%, var(--accent-deep) 100%)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: '14px', fontWeight: 700, color: '#fff',
          boxShadow: '0 2px 8px var(--accent-glow)',
        }}>
          N
        </div>
        <div className="t-display" style={{
          fontSize: '17px', fontWeight: 500,
        }}>
          NSE <em>Arena</em>
        </div>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: '2px', flex: 1 }}>
        {NAV_ITEMS.map(item => {
          const isActive = activeScreen === item.key;
          return (
            <button
              key={item.key}
              onClick={() => onNavigate(item.key)}
              style={{
                display: 'flex', alignItems: 'center', gap: '6px',
                padding: '7px 14px',
                fontSize: '12.5px', fontWeight: isActive ? 600 : 450,
                color: isActive ? 'var(--ink)' : 'var(--muted)',
                background: isActive ? 'var(--paper-lift)' : 'transparent',
                border: isActive ? '1px solid var(--faint)' : '1px solid transparent',
                borderRadius: 'var(--r-input)',
                cursor: 'pointer',
                transition: `all var(--dur-fast) var(--ease-swift)`,
                position: 'relative',
              }}
              onMouseEnter={e => {
                if (!isActive) {
                  e.currentTarget.style.color = 'var(--body-color)';
                  e.currentTarget.style.background = 'var(--paper-lift)';
                }
              }}
              onMouseLeave={e => {
                if (!isActive) {
                  e.currentTarget.style.color = 'var(--muted)';
                  e.currentTarget.style.background = 'transparent';
                }
              }}
            >
              <span style={{ opacity: isActive ? 1 : 0.5, transition: `opacity var(--dur-fast) var(--ease-swift)` }}>
                {item.icon}
              </span>
              {item.label}
            </button>
          );
        })}
      </div>

      {/* Right side */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        {/* Season badge */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: '6px',
          fontSize: '11px', color: 'var(--accent)',
          background: 'var(--accent-soft)', border: '1px solid var(--accent-glow)',
          padding: '4px 12px', borderRadius: 'var(--r-pill)',
          fontFamily: '"JetBrains Mono", monospace', fontWeight: 500,
        }}>
          <span style={{
            width: '5px', height: '5px', borderRadius: '50%',
            background: 'var(--accent)',
            animation: 'pulse 2s infinite',
          }} />
          {seasonLabel}
        </div>

        {/* User avatar */}
        <div style={{
          width: '32px', height: '32px', borderRadius: '50%',
          background: 'linear-gradient(135deg, var(--accent-soft) 0%, var(--paper-lift) 100%)',
          border: '2px solid var(--accent-glow)',
          fontSize: '11px', fontWeight: 600,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: 'var(--accent)',
          cursor: 'pointer',
          transition: `all var(--dur-fast) var(--ease-swift)`,
        }}>
          {user?.initials || '??'}
        </div>

        {/* Logout */}
        {onLogout && (
          <button
            onClick={onLogout}
            style={{
              padding: '5px 12px',
              fontSize: '11px', fontWeight: 500,
              color: 'var(--muted)',
              background: 'transparent',
              border: '1px solid var(--faint)',
              borderRadius: 'var(--r-pill)',
              cursor: 'pointer',
              transition: `all var(--dur-fast) var(--ease-swift)`,
            }}
            onMouseEnter={e => {
              e.target.style.color = 'var(--error)';
              e.target.style.borderColor = 'var(--error-glow)';
              e.target.style.background = 'var(--error-soft)';
            }}
            onMouseLeave={e => {
              e.target.style.color = 'var(--muted)';
              e.target.style.borderColor = 'var(--faint)';
              e.target.style.background = 'transparent';
            }}
          >
            Sign out
          </button>
        )}
      </div>
    </nav>
  );
}
