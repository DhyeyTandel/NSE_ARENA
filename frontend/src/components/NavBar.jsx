// components/NavBar.jsx
const NAV_ITEMS = [
  { key: 'dashboard', label: 'Dashboard' },
  { key: 'leaderboard', label: 'Leaderboard' },
  { key: 'scripts', label: 'Scripts' },
  { key: 'ai-feed', label: 'AI agents' },
];

export function NavBar({ activeScreen, onNavigate, user, onLogout }) {
  return (
    <nav style={{
      position: 'sticky', top: 0, zIndex: 100,
      display: 'flex', alignItems: 'center', gap: '32px',
      padding: '0 32px', height: '60px',
      background: 'var(--paper-lift)',
      borderBottom: '1px solid var(--faint)',
    }}>
      {/* Logo */}
      <div
        onClick={() => onNavigate('dashboard')}
        style={{ display: 'flex', alignItems: 'baseline', gap: '8px', cursor: 'pointer' }}
      >
        <span style={{
          width: '7px', height: '7px', borderRadius: '999px',
          background: 'var(--accent)', display: 'inline-block',
          transform: 'translateY(-1px)',
        }} />
        <span style={{
          fontFamily: '"Newsreader", Georgia, serif',
          fontSize: '21px', fontWeight: 500, letterSpacing: '-0.02em',
          color: 'var(--ink)',
        }}>
          NSE Arena
        </span>
      </div>

      {/* Pill tabs */}
      <div style={{ display: 'flex', gap: '4px', fontSize: '14.5px', fontWeight: 560 }}>
        {NAV_ITEMS.map(item => {
          const isActive = activeScreen === item.key;
          return (
            <button
              key={item.key}
              onClick={() => onNavigate(item.key)}
              style={{
                padding: '6px 14px', borderRadius: '999px',
                border: 'none', cursor: 'pointer',
                fontFamily: 'inherit', fontSize: 'inherit', fontWeight: 'inherit',
                background: isActive ? 'var(--ink)' : 'transparent',
                color: isActive ? 'var(--paper)' : 'var(--muted)',
                transition: 'all var(--dur-fast) var(--ease-swift)',
              }}
              onMouseEnter={e => { if (!isActive) e.currentTarget.style.color = 'var(--ink)'; }}
              onMouseLeave={e => { if (!isActive) e.currentTarget.style.color = 'var(--muted)'; }}
            >
              {item.label}
            </button>
          );
        })}
      </div>

      {/* Right side */}
      <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '14px' }}>
        {onLogout && (
          <button
            onClick={onLogout}
            style={{
              padding: '5px 14px', fontSize: '12px', fontWeight: 500,
              color: 'var(--muted)', background: 'transparent',
              border: '1px solid var(--faint)', borderRadius: '999px',
              cursor: 'pointer', fontFamily: 'inherit',
              transition: 'all var(--dur-fast) var(--ease-swift)',
            }}
            onMouseEnter={e => {
              e.currentTarget.style.color = 'var(--error)';
              e.currentTarget.style.borderColor = 'var(--error-glow)';
            }}
            onMouseLeave={e => {
              e.currentTarget.style.color = 'var(--muted)';
              e.currentTarget.style.borderColor = 'var(--faint)';
            }}
          >
            Sign out
          </button>
        )}
        <div
          onClick={() => onNavigate('profile')}
          style={{
            width: '32px', height: '32px', borderRadius: '999px',
            background: activeScreen === 'profile' ? 'var(--ink)' : 'var(--accent-soft)',
            color: activeScreen === 'profile' ? 'var(--paper)' : 'var(--accent-deep)',
            display: 'grid', placeItems: 'center',
            fontWeight: 600, fontSize: '13px', cursor: 'pointer',
            transition: 'all var(--dur-fast) var(--ease-swift)',
          }}
        >
          {user?.initials || '??'}
        </div>
      </div>
    </nav>
  );
}
