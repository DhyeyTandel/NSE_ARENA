// components/KpiCard.jsx
export function KpiCard({ label, value, sub, variant, icon, delay = 0 }) {
  const colors = {
    default: 'var(--ink)',
    up: 'var(--success)',
    down: 'var(--error)',
    gold: 'var(--accent)',
    blue: 'var(--blurple)',
  };

  const accentBorders = {
    up: 'var(--success)',
    down: 'var(--error)',
    gold: 'var(--accent)',
    blue: 'var(--blurple)',
  };

  const bgGradients = {
    up: 'linear-gradient(135deg, rgba(30,138,90,0.05) 0%, transparent 60%)',
    down: 'linear-gradient(135deg, rgba(208,52,44,0.05) 0%, transparent 60%)',
    gold: 'linear-gradient(135deg, rgba(238,83,8,0.06) 0%, transparent 60%)',
    blue: 'linear-gradient(135deg, rgba(91,77,242,0.05) 0%, transparent 60%)',
  };

  const iconMap = {
    portfolio: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M21 12V7H5a2 2 0 0 1 0-4h14v4"/>
        <path d="M3 5v14a2 2 0 0 0 2 2h16v-5"/>
        <path d="M18 12a2 2 0 0 0 0 4h4v-4Z"/>
      </svg>
    ),
    pnl: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="m22 7-8.5 8.5-5-5L2 17"/>
        <path d="M16 7h6v6"/>
      </svg>
    ),
    score: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
      </svg>
    ),
    rank: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <line x1="12" y1="20" x2="12" y2="10"/>
        <line x1="18" y1="20" x2="18" y2="4"/>
        <line x1="6" y1="20" x2="6" y2="16"/>
      </svg>
    ),
  };

  return (
    <div style={{
      padding: '20px 22px',
      borderRight: '1px solid var(--faint)',
      position: 'relative',
      overflow: 'hidden',
      background: bgGradients[variant] || 'none',
      borderLeft: accentBorders[variant] ? `2px solid ${accentBorders[variant]}` : 'none',
      animation: `fadeInUp 0.5s var(--ease-swift) ${delay}s both`,
      transition: `background var(--dur) var(--ease-swift)`,
      cursor: 'default',
    }}>
      {/* Header with icon */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: '6px',
        marginBottom: '10px',
      }}>
        {icon && iconMap[icon] && (
          <span style={{
            color: colors[variant] || 'var(--muted)',
            opacity: 0.6,
            display: 'flex',
          }}>
            {iconMap[icon]}
          </span>
        )}
        <div className="t-label">
          {label}
        </div>
      </div>

      {/* Value */}
      <div style={{
        fontFamily: '"JetBrains Mono", monospace', fontSize: '26px',
        fontWeight: 400, letterSpacing: '-.02em', lineHeight: 1,
        color: colors[variant] || colors.default,
        transition: `color var(--dur) var(--ease-swift)`,
      }}>
        {value}
      </div>

      {/* Sub text */}
      {sub && (
        <div style={{
          fontSize: '11.5px', color: 'var(--muted)',
          marginTop: '6px', fontFamily: '"JetBrains Mono", monospace',
        }}>
          {sub}
        </div>
      )}
    </div>
  );
}
