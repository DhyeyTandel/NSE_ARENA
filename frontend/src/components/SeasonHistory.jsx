// components/SeasonHistory.jsx
export function SeasonHistory({ seasons }) {
  if (!seasons || seasons.length === 0) {
    return (
      <div style={{
        padding: '32px 24px',
        display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '10px',
        animation: 'fadeIn 0.4s var(--ease-swift)',
      }}>
        <div style={{
          width: '44px', height: '44px', borderRadius: '50%',
          background: 'var(--paper-lift)', border: '1px solid var(--faint)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: '18px', color: 'var(--accent)',
        }}>✦</div>
        <div style={{ fontSize: '13px', fontWeight: 500, color: 'var(--body-color)' }}>
          Your first season is underway
        </div>
        <div style={{ fontSize: '12px', color: 'var(--muted)', textAlign: 'center', maxWidth: '280px' }}>
          Complete a full trading season to see your historical performance and grades here
        </div>
      </div>
    );
  }

  return (
    <div style={{ padding: '22px 24px' }}>
      <div className="t-eyebrow" style={{ marginBottom: '14px' }}>Season history</div>

      <div style={{
        display: 'grid', gridTemplateColumns: '1fr 80px 80px 72px 72px',
        gap: '8px', padding: '8px 12px',
        borderBottom: '1px solid var(--faint)',
        background: 'var(--paper-lift)', borderRadius: 'var(--r-input) var(--r-input) 0 0',
      }}>
        {['Season', 'Final Value', 'Return', 'Score', 'Grade'].map(h => (
          <div key={h} className="t-label">{h}</div>
        ))}
      </div>

      {seasons.map((s, i) => (
        <div key={i} style={{
          display: 'grid', gridTemplateColumns: '1fr 80px 80px 72px 72px',
          gap: '8px', padding: '10px 12px',
          borderBottom: '1px solid var(--faint)',
          animation: `fadeInUp 0.3s var(--ease-swift) ${i * 0.05}s both`,
        }}
          onMouseEnter={e => { e.currentTarget.style.background = 'var(--paper-lift)'; }}
          onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; }}
        >
          <div style={{ fontSize: '13px', fontWeight: 600 }}>{s.name}</div>
          <div style={{ fontFamily: '"JetBrains Mono", monospace', fontSize: '13px', color: 'var(--body-color)' }}>₹{s.finalValue?.toLocaleString('en-IN')}</div>
          <div style={{ fontFamily: '"JetBrains Mono", monospace', fontSize: '13px', color: s.returnPct >= 0 ? 'var(--success)' : 'var(--error)' }}>{s.returnPct >= 0 ? '+' : ''}{s.returnPct}%</div>
          <div style={{ fontFamily: '"JetBrains Mono", monospace', fontSize: '13px', color: 'var(--accent)' }}>{s.score}</div>
          <div style={{ fontSize: '12px', color: 'var(--body-color)' }}>{s.grade}</div>
        </div>
      ))}
    </div>
  );
}
