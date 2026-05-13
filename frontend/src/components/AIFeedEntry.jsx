// components/AIFeedEntry.jsx
import { useState } from 'react';

export function AIFeedEntry({ action, ticker, detail, time, reasoning, confidence, stats, status }) {
  const [expanded, setExpanded] = useState(true);
  const accentColors = { buy: 'var(--up)', sell: 'var(--dn)', hold: 'var(--dim)' };
  const tagStyles = {
    buy:  { color: '#000', background: 'var(--up)', fontWeight: 600 },
    sell: { color: '#fff', background: 'var(--dn)', fontWeight: 600 },
    hold: { color: 'var(--text3)', background: 'var(--ink3)', border: '1px solid var(--border2)' },
  };

  return (
    <div style={{
      border: '1px solid var(--border2)', borderRadius: 'var(--r2)',
      padding: '16px 18px', background: 'var(--ink2)',
      borderLeft: `3px solid ${accentColors[action]}`,
      transition: 'border-color 0.2s, box-shadow 0.2s',
      animation: 'fadeInUp 0.4s var(--ease)',
    }}
      onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--border3)'; e.currentTarget.style.boxShadow = 'var(--shadow-sm)'; }}
      onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--border2)'; e.currentTarget.style.boxShadow = 'none'; }}
    >
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '12px' }}>
        <span style={{
          fontSize: '10px', letterSpacing: '.08em', textTransform: 'uppercase',
          padding: '3px 10px', borderRadius: 'var(--r4)', ...tagStyles[action],
        }}>{action}</span>
        <span style={{ fontSize: '14px', fontWeight: 600, fontFamily: 'DM Mono, monospace' }}>{ticker}</span>
        <span style={{ fontSize: '12px', color: 'var(--text3)', fontFamily: 'DM Mono, monospace', marginLeft: 'auto' }}>{detail}</span>
        <span style={{ fontSize: '11px', color: 'var(--text3)', fontFamily: 'DM Mono, monospace' }}>{time}</span>
      </div>

      {/* Reasoning — collapsible */}
      <button onClick={() => setExpanded(!expanded)} style={{
        width: '100%', background: 'none', border: 'none', padding: 0,
        textAlign: 'left', cursor: 'pointer', color: 'inherit',
      }}>
        <div style={{
          fontSize: '12.5px', color: 'var(--text2)', lineHeight: 1.7,
          marginBottom: expanded ? '14px' : '0',
          maxHeight: expanded ? '200px' : '0',
          overflow: 'hidden', transition: 'max-height 0.3s var(--ease), margin 0.3s',
          fontStyle: 'italic', opacity: 0.85,
          paddingLeft: '12px', borderLeft: '2px solid var(--border2)',
        }}>
          "{reasoning}"
        </div>
      </button>

      {/* Stats + confidence */}
      <div style={{ display: 'flex', gap: '16px', alignItems: 'center', flexWrap: 'wrap' }}>
        {stats.map(({ label, value, highlight }) => (
          <div key={label} style={{ fontSize: '11px', color: 'var(--text3)' }}>
            {label}{' '}
            <span style={{ fontFamily: 'DM Mono, monospace', fontWeight: 500, color: highlight || 'var(--text2)' }}>{value}</span>
          </div>
        ))}

        {/* Confidence bar */}
        <div style={{ flex: 1, minWidth: '60px', display: 'flex', alignItems: 'center', gap: '8px', marginLeft: '8px' }}>
          <div style={{ flex: 1, height: '3px', background: 'var(--border2)', borderRadius: '2px', overflow: 'hidden' }}>
            <div style={{
              height: '100%', borderRadius: '2px',
              width: `${confidence}%`,
              background: action === 'sell' ? 'var(--dn)' : action === 'hold' ? 'var(--dim)' : 'var(--up)',
              transition: 'width 0.6s var(--ease)',
            }} />
          </div>
          <span style={{ fontSize: '10px', fontFamily: 'DM Mono, monospace', color: 'var(--text3)', whiteSpace: 'nowrap' }}>{confidence}%</span>
        </div>

        {status && (
          <div style={{ fontSize: '11px', fontWeight: 500, color: status.includes('Blocked') ? 'var(--dn)' : 'var(--up)' }}>{status}</div>
        )}
      </div>
    </div>
  );
}
