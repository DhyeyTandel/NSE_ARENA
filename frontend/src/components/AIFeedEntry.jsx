// components/AIFeedEntry.jsx
import { useState } from 'react';

export function AIFeedEntry({ action, ticker, detail, time, reasoning, confidence, stats, status }) {
  const [expanded, setExpanded] = useState(true);
  const accentColors = { buy: 'var(--success)', sell: 'var(--error)', hold: 'var(--muted-soft)' };
  const tagStyles = {
    buy:  { color: '#fff', background: 'var(--success)', fontWeight: 600 },
    sell: { color: '#fff', background: 'var(--error)', fontWeight: 600 },
    hold: { color: 'var(--muted)', background: 'var(--paper-lift)', border: '1px solid var(--faint)' },
  };

  return (
    <div style={{
      border: '1px solid var(--faint)', borderRadius: 'var(--r-card)',
      padding: '16px 18px', background: 'var(--card)',
      borderLeft: `3px solid ${accentColors[action]}`,
      transition: `border-color var(--dur-fast) var(--ease-swift), box-shadow var(--dur-fast) var(--ease-swift)`,
      animation: 'fadeInUp 0.4s var(--ease-swift)',
    }}
      onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--ink-soft)'; e.currentTarget.style.boxShadow = 'var(--shadow-soft)'; }}
      onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--faint)'; e.currentTarget.style.boxShadow = 'none'; }}
    >
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '12px' }}>
        <span style={{
          fontSize: '10px', letterSpacing: '.08em', textTransform: 'uppercase',
          padding: '3px 10px', borderRadius: 'var(--r-pill)', ...tagStyles[action],
        }}>{action}</span>
        <span style={{ fontSize: '14px', fontWeight: 600, fontFamily: '"JetBrains Mono", monospace' }}>{ticker}</span>
        <span style={{ fontSize: '12px', color: 'var(--muted)', fontFamily: '"JetBrains Mono", monospace', marginLeft: 'auto' }}>{detail}</span>
        <span style={{ fontSize: '11px', color: 'var(--muted)', fontFamily: '"JetBrains Mono", monospace' }}>{time}</span>
      </div>

      {/* Reasoning — collapsible */}
      <button onClick={() => setExpanded(!expanded)} style={{
        width: '100%', background: 'none', border: 'none', padding: 0,
        textAlign: 'left', cursor: 'pointer', color: 'inherit',
      }}>
        <div style={{
          fontSize: '12.5px', color: 'var(--body-color)', lineHeight: 1.7,
          marginBottom: expanded ? '14px' : '0',
          maxHeight: expanded ? '200px' : '0',
          overflow: 'hidden', transition: `max-height var(--dur) var(--ease-swift), margin var(--dur) var(--ease-swift)`,
          fontStyle: 'italic', opacity: 0.85,
          paddingLeft: '12px', borderLeft: '2px solid var(--faint)',
        }}>
          "{reasoning}"
        </div>
      </button>

      {/* Stats + confidence */}
      <div style={{ display: 'flex', gap: '16px', alignItems: 'center', flexWrap: 'wrap' }}>
        {stats.map(({ label, value, highlight }) => (
          <div key={label} style={{ fontSize: '11px', color: 'var(--muted)' }}>
            {label}{' '}
            <span style={{ fontFamily: '"JetBrains Mono", monospace', fontWeight: 500, color: highlight || 'var(--body-color)' }}>{value}</span>
          </div>
        ))}

        {/* Confidence bar */}
        <div style={{ flex: 1, minWidth: '60px', display: 'flex', alignItems: 'center', gap: '8px', marginLeft: '8px' }}>
          <div style={{ flex: 1, height: '3px', background: 'var(--faint)', borderRadius: '2px', overflow: 'hidden' }}>
            <div style={{
              height: '100%', borderRadius: '2px',
              width: `${confidence}%`,
              background: action === 'sell' ? 'var(--error)' : action === 'hold' ? 'var(--muted-soft)' : 'var(--success)',
              transition: `width var(--dur-slow) var(--ease-swift)`,
            }} />
          </div>
          <span style={{ fontSize: '10px', fontFamily: '"JetBrains Mono", monospace', color: 'var(--muted)', whiteSpace: 'nowrap' }}>{confidence}%</span>
        </div>

        {status && (
          <div style={{ fontSize: '11px', fontWeight: 500, color: status.includes('Blocked') ? 'var(--error)' : 'var(--success)' }}>{status}</div>
        )}
      </div>
    </div>
  );
}
