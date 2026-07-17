// components/TraderScoreCard.jsx
export function TraderScoreCard({ score, grade, breakdown }) {
  const barColors = {
    returns: 'linear-gradient(90deg, var(--blurple) 0%, #4438D6 100%)',
    risk: 'linear-gradient(90deg, var(--success) 0%, #156B45 100%)',
    consistency: 'linear-gradient(90deg, var(--accent) 0%, var(--accent-deep) 100%)',
    discipline: 'linear-gradient(90deg, var(--magenta) 0%, #B82E80 100%)',
  };
  const barBg = {
    returns: 'var(--blurple)',
    risk: 'var(--success)',
    consistency: 'var(--accent)',
    discipline: 'var(--magenta)',
  };

  return (
    <div style={{ padding: '22px 24px' }}>
      <div className="t-eyebrow" style={{ marginBottom: '18px', display: 'flex', alignItems: 'center', gap: '8px' }}>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M22 12h-4l-3 9L9 3l-3 9H2"/>
        </svg>
        Score breakdown
      </div>

      {breakdown.map(({ key, label, weight, score: s }) => (
        <div key={key} style={{
          display: 'flex', alignItems: 'center', gap: '14px', marginBottom: '12px',
        }}>
          <div style={{
            fontSize: '12px', color: 'var(--body-color)', width: '140px', flexShrink: 0,
            display: 'flex', alignItems: 'center', gap: '6px',
          }}>
            <span style={{
              width: '8px', height: '8px', borderRadius: '2px',
              background: barBg[key], flexShrink: 0,
            }} />
            {label}
            <span style={{ color: 'var(--muted)', fontSize: '10px' }}>({weight}%)</span>
          </div>
          <div style={{
            flex: 1, height: '6px', background: 'var(--faint)',
            borderRadius: '3px', overflow: 'hidden',
          }}>
            <div style={{
              height: '100%', borderRadius: '3px',
              width: `${s}%`,
              background: barColors[key],
              transition: `width var(--dur-slow) var(--ease-swift)`,
              boxShadow: s > 0 ? `0 0 8px ${barBg[key]}40` : 'none',
            }} />
          </div>
          <div style={{
            fontSize: '12px', fontFamily: '"JetBrains Mono", monospace', fontWeight: 500,
            color: s > 0 ? 'var(--body-color)' : 'var(--muted)',
            width: '28px', textAlign: 'right', flexShrink: 0,
          }}>
            {s}
          </div>
        </div>
      ))}
    </div>
  );
}
