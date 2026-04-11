// components/AIFeedEntry.jsx
export function AIFeedEntry({ action, ticker, detail, time, reasoning, confidence, stats, status }) {
  const accentColors = { buy: 'var(--up)', sell: 'var(--dn)', hold: 'var(--dim)' };
  const tagStyles = {
    buy:  { color: 'var(--up)', background: 'var(--up-dim)', border: '1px solid #34d39920' },
    sell: { color: 'var(--dn)', background: 'var(--dn-dim)', border: '1px solid #f8717120' },
    hold: { color: 'var(--text3)', background: 'var(--ink3)', border: '1px solid var(--border2)' }
  };

  return (
    <div style={{
      border: '1px solid var(--border2)', borderRadius: 'var(--r2)',
      padding: '14px', background: 'var(--ink2)',
      borderLeft: `2px solid ${accentColors[action]}`
    }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px' }}>
        <span style={{
          fontSize: '9px', fontWeight: 600, letterSpacing: '.08em',
          textTransform: 'uppercase', padding: '2px 7px', borderRadius: '3px',
          fontFamily: 'DM Mono, monospace', ...tagStyles[action]
        }}>
          {action}
        </span>
        <span style={{ fontSize: '13px', fontWeight: 500, fontFamily: 'DM Mono, monospace' }}>
          {ticker}
        </span>
        <span style={{ fontSize: '11px', color: 'var(--text3)',
          fontFamily: 'DM Mono, monospace', marginLeft: 'auto' }}>
          {detail}
        </span>
        <span style={{ fontSize: '10px', color: 'var(--text3)', fontFamily: 'DM Mono, monospace' }}>
          {time}
        </span>
      </div>

      {/* Reasoning — this is the key feature, display it like prose */}
      <div style={{
        fontSize: '12px', color: 'var(--text2)', lineHeight: 1.65,
        marginBottom: '10px', fontWeight: 300
      }}>
        "{reasoning}"
      </div>

      {/* Stats row + confidence bar */}
      <div style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
        {stats.map(({ label, value, highlight }) => (
          <div key={label} style={{ fontSize: '10px', color: 'var(--text3)' }}>
            {label}{' '}
            <span style={{
              fontFamily: 'DM Mono, monospace',
              color: highlight || 'var(--text2)'
            }}>
              {value}
            </span>
          </div>
        ))}
        <div style={{
          flex: 1, height: '2px', background: 'var(--border2)',
          borderRadius: '1px', overflow: 'hidden', marginLeft: '8px'
        }}>
          <div style={{
            height: '100%', borderRadius: '1px',
            width: `${confidence}%`,
            background: action === 'sell' ? 'var(--dn)' : action === 'hold' ? 'var(--dim)' : 'var(--up)',
            transition: '.4s'
          }} />
        </div>
        {status && (
          <div style={{ fontSize: '10px', color: 'var(--up)', marginLeft: '8px' }}>
            {status}
          </div>
        )}
      </div>
    </div>
  );
}
