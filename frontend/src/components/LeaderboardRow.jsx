// components/LeaderboardRow.jsx
export function LeaderboardRow({ rank, trader, score, grade, returnPct, drawdown, value, isYou, isAI }) {
  const gradeStyles = {
    Elite: { color: 'var(--gold)', background: 'var(--gold-dim)', border: '1px solid var(--gold-glow)' },
    Pro:   { color: 'var(--blue)', background: 'var(--blue-dim)', border: '1px solid #60a5fa22' },
    Inter: { color: 'var(--up)',   background: 'var(--up-dim)',   border: '1px solid #34d39922' },
  };

  const rankColors = { 1: 'var(--gold)', 2: '#94a3b8', 3: '#9a7c5a' };

  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: '36px 1fr 88px 76px 76px 72px',
      alignItems: 'center',
      padding: '11px 20px',
      borderBottom: '1px solid var(--border)',
      borderLeft: isYou ? '1px solid var(--gold)' : 'none',
      background: isYou ? '#ffffff03' : isAI ? '#60a5fa04' : 'none',
      gap: '8px',
      cursor: 'default',
      transition: 'background .1s'
    }}>
      <div style={{
        fontFamily: 'DM Mono, monospace', fontSize: '12px',
        color: rankColors[rank] || 'var(--text3)'
      }}>
        {rank}
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
        <div style={{
          width: '28px', height: '28px', borderRadius: '50%',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: '10px', fontWeight: 600, flexShrink: 0,
          border: '1px solid var(--border2)',
          background: isYou ? 'var(--gold-dim)' : isAI ? 'var(--blue-dim)' : 'var(--ink3)',
          borderColor: isYou ? 'var(--gold-glow)' : isAI ? '#60a5fa22' : 'var(--border2)',
          color: isYou ? 'var(--gold)' : isAI ? 'var(--blue)' : 'var(--text3)'
        }}>
          {trader.initials}
        </div>
        <div>
          <div style={{ fontSize: '12px', fontWeight: 500 }}>
            {trader.name}
            {isAI && (
              <span style={{
                fontSize: '9px', color: 'var(--blue)',
                background: 'var(--blue-dim)', border: '1px solid #60a5fa20',
                padding: '1px 5px', borderRadius: '2px', marginLeft: '6px'
              }}>
                Gemini
              </span>
            )}
          </div>
          <div style={{ fontSize: '10px', color: 'var(--text3)', marginTop: '1px' }}>
            {trader.tag}
          </div>
        </div>
      </div>

      <div>
        <span style={{
          fontSize: '10px', fontWeight: 500, padding: '2px 7px',
          borderRadius: '3px', fontFamily: 'DM Mono, monospace',
          ...gradeStyles[grade]
        }}>
          {score}
        </span>
      </div>

      <div style={{ fontFamily: 'DM Mono, monospace', fontSize: '12px', color: 'var(--up)' }}>
        {returnPct}
      </div>

      <div style={{
        fontFamily: 'DM Mono, monospace', fontSize: '12px',
        color: parseFloat(drawdown) > -5 ? 'var(--up)' : parseFloat(drawdown) > -10 ? 'var(--gold)' : 'var(--dn)'
      }}>
        {drawdown}
      </div>

      <div style={{ fontFamily: 'DM Mono, monospace', fontSize: '12px', color: 'var(--text2)' }}>
        {value}
      </div>
    </div>
  );
}
