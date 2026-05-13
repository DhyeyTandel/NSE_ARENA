// components/LeaderboardRow.jsx
export function LeaderboardRow({ rank, trader, score, grade, returnPct, drawdown, value, isYou, isAI }) {
  const gradeStyles = {
    Elite:    { color: 'var(--gold)', background: 'var(--gold-dim)', border: '1px solid var(--gold-glow)' },
    Pro:      { color: 'var(--blue)', background: 'var(--blue-dim)', border: '1px solid var(--blue-glow)' },
    Inter:    { color: 'var(--up)',   background: 'var(--up-dim)',   border: '1px solid var(--up-glow)' },
    Beginner: { color: 'var(--text3)', background: 'var(--ink3)', border: '1px solid var(--border2)' },
  };
  const rankMedals = { 1: '🥇', 2: '🥈', 3: '🥉' };
  const rankColors = { 1: 'var(--gold)', 2: '#94a3b8', 3: '#cd7f32' };
  const isReturnPositive = returnPct && returnPct.startsWith('+');

  return (
    <div style={{
      display: 'grid', gridTemplateColumns: '40px 1fr 88px 80px 80px 80px',
      alignItems: 'center', padding: '12px 24px',
      borderBottom: '1px solid var(--border)',
      borderLeft: isYou ? '2px solid var(--gold)' : '2px solid transparent',
      background: isYou ? 'rgba(212,168,67,0.03)' : isAI ? 'rgba(108,158,255,0.02)' : 'transparent',
      gap: '8px', cursor: 'default', transition: 'background 0.2s var(--ease)',
      animation: `fadeInUp 0.4s var(--ease) ${rank * 0.05}s both`,
    }}
      onMouseEnter={e => { e.currentTarget.style.background = isYou ? 'rgba(212,168,67,0.05)' : isAI ? 'rgba(108,158,255,0.04)' : 'var(--ink2)'; }}
      onMouseLeave={e => { e.currentTarget.style.background = isYou ? 'rgba(212,168,67,0.03)' : isAI ? 'rgba(108,158,255,0.02)' : 'transparent'; }}
    >
      <div style={{ fontFamily: 'DM Mono, monospace', fontSize: '13px', fontWeight: 600, color: rankColors[rank] || 'var(--text3)' }}>
        {rankMedals[rank] || rank}
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        <div style={{
          width: '32px', height: '32px', borderRadius: '50%',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: '11px', fontWeight: 600, flexShrink: 0,
          background: isYou ? 'var(--gold-dim)' : isAI ? 'var(--blue-dim)' : 'var(--ink3)',
          border: isYou ? '2px solid var(--gold-glow)' : isAI ? '2px solid var(--blue-glow)' : '1px solid var(--border2)',
          color: isYou ? 'var(--gold)' : isAI ? 'var(--blue)' : 'var(--text3)',
        }}>{trader.initials}</div>
        <div>
          <div style={{ fontSize: '13px', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '6px' }}>
            {trader.name}
            {isAI && <span style={{ fontSize: '9px', fontWeight: 600, color: 'var(--blue)', background: 'var(--blue-dim)', border: '1px solid var(--blue-glow)', padding: '1px 6px', borderRadius: 'var(--r4)' }}>AI</span>}
            {isYou && <span style={{ fontSize: '9px', fontWeight: 600, color: 'var(--gold)', background: 'var(--gold-dim)', border: '1px solid var(--gold-glow)', padding: '1px 6px', borderRadius: 'var(--r4)' }}>You</span>}
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text3)', marginTop: '1px' }}>{trader.tag}</div>
        </div>
      </div>
      <div>
        <span style={{ fontSize: '11px', fontWeight: 600, padding: '3px 10px', borderRadius: 'var(--r4)', fontFamily: 'DM Mono, monospace', ...(gradeStyles[grade] || gradeStyles.Beginner) }}>{score}</span>
      </div>
      <div style={{ fontFamily: 'DM Mono, monospace', fontSize: '13px', color: isReturnPositive ? 'var(--up)' : 'var(--dn)', fontWeight: 500 }}>{returnPct}</div>
      <div style={{ fontFamily: 'DM Mono, monospace', fontSize: '13px', color: parseFloat(drawdown) > -5 ? 'var(--up)' : parseFloat(drawdown) > -10 ? 'var(--gold)' : 'var(--dn)' }}>{drawdown}</div>
      <div style={{ fontFamily: 'DM Mono, monospace', fontSize: '13px', color: 'var(--text2)' }}>{value}</div>
    </div>
  );
}
