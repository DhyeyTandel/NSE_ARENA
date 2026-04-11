// components/TraderScoreCard.jsx
export function TraderScoreCard({ score, grade, breakdown }) {
  const barColors = {
    returns: 'var(--blue)',
    risk: 'var(--up)',
    consistency: 'var(--gold)',
    discipline: '#a78bfa'
  };

  return (
    <div style={{ padding: '18px 20px' }}>
      <div style={{ fontSize: '10px', color: 'var(--text3)',
        textTransform: 'uppercase', letterSpacing: '.06em', marginBottom: '14px' }}>
        Score breakdown
      </div>

      {breakdown.map(({ key, label, weight, score: s }) => (
        <div key={key} style={{
          display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '9px'
        }}>
          <div style={{ fontSize: '11px', color: 'var(--text2)', width: '130px', flexShrink: 0 }}>
            {label} ({weight}%)
          </div>
          <div style={{
            flex: 1, height: '3px', background: 'var(--border2)',
            borderRadius: '2px', overflow: 'hidden'
          }}>
            <div style={{
              height: '100%', borderRadius: '2px',
              width: `${s}%`, background: barColors[key],
              transition: 'width .5s ease'
            }} />
          </div>
          <div style={{
            fontSize: '11px', fontFamily: 'DM Mono, monospace',
            color: 'var(--text3)', width: '24px', textAlign: 'right', flexShrink: 0
          }}>
            {s}
          </div>
        </div>
      ))}
    </div>
  );
}
