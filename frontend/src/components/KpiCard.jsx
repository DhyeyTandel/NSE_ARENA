// components/KpiCard.jsx
export function KpiCard({ label, value, sub, variant, icon, delay = 0 }) {
  const colors = {
    default: 'var(--text)',
    up: 'var(--up)',
    down: 'var(--dn)',
    gold: 'var(--gold)',
    blue: 'var(--blue)',
  };

  const accentBorders = {
    up: 'var(--up)',
    down: 'var(--dn)',
    gold: 'var(--gold)',
    blue: 'var(--blue)',
  };

  const bgGradients = {
    up: 'linear-gradient(135deg, rgba(34,201,130,0.04) 0%, transparent 60%)',
    down: 'linear-gradient(135deg, rgba(239,68,68,0.04) 0%, transparent 60%)',
    gold: 'linear-gradient(135deg, rgba(212,168,67,0.05) 0%, transparent 60%)',
    blue: 'linear-gradient(135deg, rgba(108,158,255,0.04) 0%, transparent 60%)',
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
      borderRight: '1px solid var(--border)',
      position: 'relative',
      overflow: 'hidden',
      background: bgGradients[variant] || 'none',
      borderLeft: accentBorders[variant] ? `2px solid ${accentBorders[variant]}` : 'none',
      animation: `fadeInUp 0.5s var(--ease) ${delay}s both`,
      transition: 'background 0.3s var(--ease)',
      cursor: 'default',
    }}>
      {/* Header with icon */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: '6px',
        marginBottom: '10px',
      }}>
        {icon && iconMap[icon] && (
          <span style={{
            color: colors[variant] || 'var(--text3)',
            opacity: 0.6,
            display: 'flex',
          }}>
            {iconMap[icon]}
          </span>
        )}
        <div style={{
          fontSize: '11px', fontWeight: 500, color: 'var(--text3)',
          textTransform: 'uppercase', letterSpacing: '.08em',
        }}>
          {label}
        </div>
      </div>

      {/* Value */}
      <div style={{
        fontFamily: 'DM Mono, monospace', fontSize: '26px',
        fontWeight: 400, letterSpacing: '-.5px', lineHeight: 1,
        color: colors[variant] || colors.default,
        transition: 'color 0.3s',
      }}>
        {value}
      </div>

      {/* Sub text */}
      {sub && (
        <div style={{
          fontSize: '11.5px', color: 'var(--text3)',
          marginTop: '6px', fontFamily: 'DM Mono, monospace',
        }}>
          {sub}
        </div>
      )}
    </div>
  );
}
