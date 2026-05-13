// components/SeasonHistory.jsx
export function SeasonHistory({ seasons }) {
  if (!seasons || seasons.length === 0) {
    return (
      <div style={{
        padding: '32px 24px',
        display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '10px',
        animation: 'fadeIn 0.4s var(--ease)',
      }}>
        <div style={{
          width: '44px', height: '44px', borderRadius: '50%',
          background: 'var(--ink2)', border: '1px solid var(--border2)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: '18px',
        }}>🏆</div>
        <div style={{ fontSize: '13px', fontWeight: 500, color: 'var(--text2)' }}>
          Your first season is underway
        </div>
        <div style={{ fontSize: '12px', color: 'var(--text3)', textAlign: 'center', maxWidth: '280px' }}>
          Complete a full trading season to see your historical performance and grades here
        </div>
      </div>
    );
  }

  return (
    <div style={{ padding: '22px 24px' }}>
      <div style={{
        fontSize: '11px', fontWeight: 500, color: 'var(--text3)',
        textTransform: 'uppercase', letterSpacing: '.08em', marginBottom: '14px',
      }}>Season History</div>

      <div style={{
        display: 'grid', gridTemplateColumns: '1fr 80px 80px 72px 72px',
        gap: '8px', padding: '8px 12px',
        borderBottom: '1px solid var(--border2)',
        background: 'var(--ink2)', borderRadius: 'var(--r) var(--r) 0 0',
      }}>
        {['Season', 'Final Value', 'Return', 'Score', 'Grade'].map(h => (
          <div key={h} style={{
            fontSize: '10px', fontWeight: 500, color: 'var(--text3)',
            textTransform: 'uppercase', letterSpacing: '.08em',
          }}>{h}</div>
        ))}
      </div>

      {seasons.map((s, i) => (
        <div key={i} style={{
          display: 'grid', gridTemplateColumns: '1fr 80px 80px 72px 72px',
          gap: '8px', padding: '10px 12px',
          borderBottom: '1px solid var(--border)',
          animation: `fadeInUp 0.3s var(--ease) ${i * 0.05}s both`,
        }}
          onMouseEnter={e => { e.currentTarget.style.background = 'var(--ink2)'; }}
          onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; }}
        >
          <div style={{ fontSize: '13px', fontWeight: 600 }}>{s.name}</div>
          <div style={{ fontFamily: 'DM Mono, monospace', fontSize: '13px', color: 'var(--text2)' }}>₹{s.finalValue?.toLocaleString('en-IN')}</div>
          <div style={{ fontFamily: 'DM Mono, monospace', fontSize: '13px', color: s.returnPct >= 0 ? 'var(--up)' : 'var(--dn)' }}>{s.returnPct >= 0 ? '+' : ''}{s.returnPct}%</div>
          <div style={{ fontFamily: 'DM Mono, monospace', fontSize: '13px', color: 'var(--gold)' }}>{s.score}</div>
          <div style={{ fontSize: '12px', color: 'var(--text2)' }}>{s.grade}</div>
        </div>
      ))}
    </div>
  );
}
