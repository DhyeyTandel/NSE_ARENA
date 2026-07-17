// components/LeaderboardRow.jsx
export function LeaderboardRow({ rank, trader, score, grade, returnPct, drawdown, value, isYou, isAI }) {
  const gradeStyles = {
    Elite:    { color: 'var(--accent)', background: 'var(--accent-soft)', border: '1px solid var(--accent-glow)' },
    Pro:      { color: 'var(--blurple)', background: 'var(--blurple-soft)', border: '1px solid var(--blurple-glow)' },
    Inter:    { color: 'var(--success)', background: 'var(--success-soft)', border: '1px solid var(--success-glow)' },
    Beginner: { color: 'var(--muted)', background: 'var(--paper-lift)', border: '1px solid var(--faint)' },
  };
  const rankColors = { 1: 'var(--accent)', 2: '#8B8378', 3: '#A6673A' };
  const isReturnPositive = returnPct && returnPct.startsWith('+');

  return (
    <div style={{
      display: 'grid', gridTemplateColumns: '40px 1fr 88px 80px 80px 80px',
      alignItems: 'center', padding: '12px 24px',
      borderBottom: '1px solid var(--faint)',
      borderLeft: isYou ? '2px solid var(--accent)' : '2px solid transparent',
      background: isYou ? 'rgba(238,83,8,0.03)' : isAI ? 'rgba(91,77,242,0.03)' : 'transparent',
      gap: '8px', cursor: 'default', transition: `background var(--dur) var(--ease-swift)`,
      animation: `fadeInUp 0.4s var(--ease-swift) ${rank * 0.05}s both`,
    }}
      onMouseEnter={e => { e.currentTarget.style.background = isYou ? 'rgba(238,83,8,0.06)' : isAI ? 'rgba(91,77,242,0.05)' : 'var(--paper-lift)'; }}
      onMouseLeave={e => { e.currentTarget.style.background = isYou ? 'rgba(238,83,8,0.03)' : isAI ? 'rgba(91,77,242,0.03)' : 'transparent'; }}
    >
      <div style={{ fontFamily: '"JetBrains Mono", monospace', fontSize: '13px', fontWeight: 600, color: rankColors[rank] || 'var(--muted)' }}>
        {rank}
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        <div style={{
          width: '32px', height: '32px', borderRadius: '50%',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: '11px', fontWeight: 600, flexShrink: 0,
          background: isYou ? 'var(--accent-soft)' : isAI ? 'var(--blurple-soft)' : 'var(--paper-lift)',
          border: isYou ? '2px solid var(--accent-glow)' : isAI ? '2px solid var(--blurple-glow)' : '1px solid var(--faint)',
          color: isYou ? 'var(--accent)' : isAI ? 'var(--blurple)' : 'var(--muted)',
        }}>{trader.initials}</div>
        <div>
          <div style={{ fontSize: '13px', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '6px' }}>
            {trader.name}
            {isAI && <span style={{ fontSize: '9px', fontWeight: 600, color: 'var(--blurple)', background: 'var(--blurple-soft)', border: '1px solid var(--blurple-glow)', padding: '1px 6px', borderRadius: 'var(--r-pill)' }}>AI</span>}
            {isYou && <span style={{ fontSize: '9px', fontWeight: 600, color: 'var(--accent)', background: 'var(--accent-soft)', border: '1px solid var(--accent-glow)', padding: '1px 6px', borderRadius: 'var(--r-pill)' }}>You</span>}
          </div>
          <div style={{ fontSize: '11px', color: 'var(--muted)', marginTop: '1px' }}>{trader.tag}</div>
        </div>
      </div>
      <div>
        <span style={{ fontSize: '11px', fontWeight: 600, padding: '3px 10px', borderRadius: 'var(--r-pill)', fontFamily: '"JetBrains Mono", monospace', ...(gradeStyles[grade] || gradeStyles.Beginner) }}>{score}</span>
      </div>
      <div style={{ fontFamily: '"JetBrains Mono", monospace', fontSize: '13px', color: isReturnPositive ? 'var(--success)' : 'var(--error)', fontWeight: 500 }}>{returnPct}</div>
      <div style={{ fontFamily: '"JetBrains Mono", monospace', fontSize: '13px', color: parseFloat(drawdown) > -5 ? 'var(--success)' : parseFloat(drawdown) > -10 ? 'var(--accent)' : 'var(--error)' }}>{drawdown}</div>
      <div style={{ fontFamily: '"JetBrains Mono", monospace', fontSize: '13px', color: 'var(--body-color)' }}>{value}</div>
    </div>
  );
}
