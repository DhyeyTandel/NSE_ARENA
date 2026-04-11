// components/NavBar.jsx
import { useState, useEffect } from 'react';

export function NavBar({ activeScreen, onNavigate, user, onLogout }) {
  const tabs = ['dashboard', 'leaderboard', 'ai-feed', 'profile'];
  const [season, setSeason] = useState(null);

  // Fetch active season info
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

  const seasonLabel = season
    ? `${season.name.replace('Season ', 'S')} · ${season.days_remaining}d`
    : 'S1 · —';

  return (
    <nav style={{
      height: '44px',
      background: 'var(--ink)',
      borderBottom: '1px solid var(--border)',
      display: 'flex',
      alignItems: 'center',
      padding: '0 18px',
      gap: '0'
    }}>
      <div style={{
        fontSize: '13px', fontWeight: '500',
        letterSpacing: '-.2px', marginRight: '28px', whiteSpace: 'nowrap'
      }}>
        nse<span style={{ color: 'var(--gold)' }}>arena</span>
      </div>

      <div style={{ display: 'flex', gap: '1px', flex: 1 }}>
        {tabs.map(tab => (
          <button key={tab}
            onClick={() => onNavigate(tab)}
            style={{
              padding: '5px 11px',
              fontSize: '12px',
              color: activeScreen === tab ? 'var(--text)' : 'var(--text3)',
              background: activeScreen === tab ? 'var(--ink3)' : 'none',
              border: 'none',
              borderRadius: 'var(--r)',
              cursor: 'pointer',
              fontFamily: 'Geist, sans-serif',
              transition: 'color .12s'
            }}>
            {tab.replace('-', ' ')}
          </button>
        ))}
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginLeft: 'auto' }}>
        <div style={{
          fontSize: '11px', color: 'var(--gold)',
          background: 'var(--gold-dim)', border: '1px solid var(--gold-glow)',
          padding: '3px 9px', borderRadius: '20px',
          fontFamily: 'DM Mono, monospace'
        }}>
          {seasonLabel}
        </div>
        <div style={{
          width: '26px', height: '26px', borderRadius: '50%',
          background: 'var(--ink3)', border: '1px solid var(--border3)',
          fontSize: '10px', fontWeight: '500', display: 'flex',
          alignItems: 'center', justifyContent: 'center', color: 'var(--text2)'
        }}>
          {user?.initials || '??'}
        </div>
        {onLogout && (
          <button
            onClick={onLogout}
            style={{
              padding: '4px 8px',
              fontSize: '10px',
              color: 'var(--text3)',
              background: 'none',
              border: '1px solid var(--border2)',
              borderRadius: 'var(--r)',
              cursor: 'pointer',
              fontFamily: 'Geist, sans-serif',
              transition: 'color .12s, border-color .12s',
            }}
            onMouseEnter={e => {
              e.target.style.color = 'var(--dn)';
              e.target.style.borderColor = 'rgba(248,113,113,0.3)';
            }}
            onMouseLeave={e => {
              e.target.style.color = 'var(--text3)';
              e.target.style.borderColor = 'var(--border2)';
            }}
          >
            logout
          </button>
        )}
      </div>
    </nav>
  );
}
