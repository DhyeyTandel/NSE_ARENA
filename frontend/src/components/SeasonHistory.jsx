// components/SeasonHistory.jsx
export function SeasonHistory({ seasons }) {
  if (!seasons || seasons.length === 0) {
    return null;
  }

  return (
    <div style={{ padding: '18px 20px' }}>
      <div style={{
        fontSize: '10px', fontWeight: 400, color: 'var(--text3)',
        textTransform: 'uppercase', letterSpacing: '.06em', marginBottom: '14px'
      }}>
        Season history
      </div>

      {/* Header */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: '1fr 80px 80px 72px 72px',
        gap: '8px', padding: '6px 0',
        borderBottom: '1px solid var(--border)',
      }}>
        {['Season', 'Final Value', 'Return', 'Score', 'Grade'].map(h => (
          <div key={h} style={{
            fontSize: '10px', color: 'var(--text3)',
            textTransform: 'uppercase', letterSpacing: '.06em'
          }}>
            {h}
          </div>
        ))}
      </div>

      {/* Rows */}
      {seasons.map((s, i) => (
        <div key={i} style={{
          display: 'grid',
          gridTemplateColumns: '1fr 80px 80px 72px 72px',
          gap: '8px', padding: '8px 0',
          borderBottom: '1px solid var(--border)',
        }}>
          <div style={{ fontSize: '12px', fontWeight: 500 }}>{s.name}</div>
          <div style={{ fontFamily: 'DM Mono, monospace', fontSize: '12px', color: 'var(--text2)' }}>
            ₹{s.finalValue?.toLocaleString('en-IN')}
          </div>
          <div style={{
            fontFamily: 'DM Mono, monospace', fontSize: '12px',
            color: s.returnPct >= 0 ? 'var(--up)' : 'var(--dn)'
          }}>
            {s.returnPct >= 0 ? '+' : ''}{s.returnPct}%
          </div>
          <div style={{ fontFamily: 'DM Mono, monospace', fontSize: '12px', color: 'var(--gold)' }}>
            {s.score}
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text2)' }}>
            {s.grade}
          </div>
        </div>
      ))}
    </div>
  );
}
