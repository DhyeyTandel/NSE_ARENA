// components/TraderScoreCard.jsx
export function TraderScoreCard({ score, grade, breakdown }) {
  const barColors = {
    returns: 'linear-gradient(90deg, var(--blue) 0%, #4e7ef7 100%)',
    risk: 'linear-gradient(90deg, var(--up) 0%, #1ab370 100%)',
    consistency: 'linear-gradient(90deg, var(--gold) 0%, var(--gold-solid) 100%)',
    discipline: 'linear-gradient(90deg, #a78bfa 0%, #8b5cf6 100%)',
  };
  const barBg = {
    returns: 'var(--blue)',
    risk: 'var(--up)',
    consistency: 'var(--gold)',
    discipline: '#a78bfa',
  };

  return (
    <div style={{ padding: '22px 24px' }}>
      <div style={{
        fontSize: '11px', fontWeight: 500, color: 'var(--text3)',
        textTransform: 'uppercase', letterSpacing: '.08em', marginBottom: '18px',
        display: 'flex', alignItems: 'center', gap: '8px',
      }}>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M22 12h-4l-3 9L9 3l-3 9H2"/>
        </svg>
        Score Breakdown
      </div>

      {breakdown.map(({ key, label, weight, score: s }) => (
        <div key={key} style={{
          display: 'flex', alignItems: 'center', gap: '14px', marginBottom: '12px',
        }}>
          <div style={{
            fontSize: '12px', color: 'var(--text2)', width: '140px', flexShrink: 0,
            display: 'flex', alignItems: 'center', gap: '6px',
          }}>
            <span style={{
              width: '8px', height: '8px', borderRadius: '2px',
              background: barBg[key], flexShrink: 0,
            }} />
            {label}
            <span style={{ color: 'var(--text3)', fontSize: '10px' }}>({weight}%)</span>
          </div>
          <div style={{
            flex: 1, height: '6px', background: 'var(--ink3)',
            borderRadius: '3px', overflow: 'hidden',
          }}>
            <div style={{
              height: '100%', borderRadius: '3px',
              width: `${s}%`,
              background: barColors[key],
              transition: 'width 0.8s var(--ease)',
              boxShadow: s > 0 ? `0 0 8px ${barBg[key]}40` : 'none',
            }} />
          </div>
          <div style={{
            fontSize: '12px', fontFamily: 'DM Mono, monospace', fontWeight: 500,
            color: s > 0 ? 'var(--text2)' : 'var(--text3)',
            width: '28px', textAlign: 'right', flexShrink: 0,
          }}>
            {s}
          </div>
        </div>
      ))}
    </div>
  );
}
