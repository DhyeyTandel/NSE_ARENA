// components/PositionsTable.jsx
import { useState, useEffect, useRef } from 'react';

export function PositionsTable({ positions, livePrices = {} }) {
  const [flashTickers, setFlashTickers] = useState({});
  const prevPrices = useRef({});

  // Detect price changes and trigger flash animation
  useEffect(() => {
    const newFlashes = {};
    for (const ticker of Object.keys(livePrices)) {
      const prev = prevPrices.current[ticker];
      const curr = livePrices[ticker]?.price;
      if (prev !== undefined && curr !== undefined && prev !== curr) {
        newFlashes[ticker] = curr > prev ? 'up' : 'down';
      }
    }

    if (Object.keys(newFlashes).length > 0) {
      setFlashTickers(newFlashes);
      const timer = setTimeout(() => setFlashTickers({}), 600);
      return () => clearTimeout(timer);
    }

    const updated = {};
    for (const [ticker, data] of Object.entries(livePrices)) {
      updated[ticker] = data.price;
    }
    prevPrices.current = updated;
  }, [livePrices]);

  if (!positions || positions.length === 0) {
    return (
      <div style={{
        padding: '32px 24px',
        display: 'flex', flexDirection: 'column',
        alignItems: 'center', gap: '12px',
        animation: 'fadeIn 0.4s var(--ease)',
      }}>
        <div style={{
          width: '48px', height: '48px', borderRadius: '50%',
          background: 'var(--ink2)', border: '1px solid var(--border2)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: '20px',
        }}>
          📊
        </div>
        <div style={{ fontSize: '13px', color: 'var(--text2)', fontWeight: 500 }}>
          No open positions
        </div>
        <div style={{ fontSize: '12px', color: 'var(--text3)', textAlign: 'center' }}>
          Place your first trade using the order panel above
        </div>
      </div>
    );
  }

  return (
    <div style={{ padding: '0 24px 20px' }}>
      {/* Section header */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: '8px',
        paddingTop: '18px', marginBottom: '12px',
      }}>
        <div style={{
          fontSize: '11px', fontWeight: 500, color: 'var(--text3)',
          textTransform: 'uppercase', letterSpacing: '.08em',
        }}>
          Open Positions
        </div>
        <div style={{
          fontSize: '10px', fontWeight: 600,
          color: 'var(--text2)', background: 'var(--ink3)',
          padding: '2px 8px', borderRadius: 'var(--r4)',
          fontFamily: 'DM Mono, monospace',
        }}>
          {positions.length}
        </div>
      </div>

      {/* Header */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: '1fr 72px 90px 90px 100px',
        gap: '8px', padding: '8px 12px',
        borderBottom: '1px solid var(--border2)',
        borderRadius: 'var(--r) var(--r) 0 0',
        background: 'var(--ink2)',
      }}>
        {['Symbol', 'Qty', 'Avg Price', 'LTP', 'P&L'].map(h => (
          <div key={h} style={{
            fontSize: '10px', fontWeight: 500, color: 'var(--text3)',
            textTransform: 'uppercase', letterSpacing: '.08em',
          }}>
            {h}
          </div>
        ))}
      </div>

      {/* Rows */}
      {positions.map((pos, i) => {
        const liveData = livePrices[pos.ticker];
        const currentPrice = liveData?.price || pos.current_price;
        const pnl = (currentPrice - pos.avg_price) * pos.quantity;
        const pnlPct = pos.avg_price > 0 ? ((currentPrice - pos.avg_price) / pos.avg_price * 100) : 0;
        const isUp = pnl >= 0;
        const flash = flashTickers[pos.ticker];

        return (
          <div key={i} style={{
            display: 'grid',
            gridTemplateColumns: '1fr 72px 90px 90px 100px',
            gap: '8px',
            padding: '10px 12px',
            borderBottom: '1px solid var(--border)',
            transition: 'background 0.3s var(--ease)',
            background: flash === 'up' ? 'var(--up-dim)'
              : flash === 'down' ? 'var(--dn-dim)' : 'transparent',
            animation: `fadeInUp 0.3s var(--ease) ${i * 0.05}s both`,
            cursor: 'default',
          }}
            onMouseEnter={e => {
              if (!flash) e.currentTarget.style.background = 'var(--ink2)';
            }}
            onMouseLeave={e => {
              if (!flash) e.currentTarget.style.background = 'transparent';
            }}
          >
            <div style={{
              fontSize: '13px', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '6px',
            }}>
              {pos.ticker}
              {pos.state === 'pending' && (
                <span style={{
                  fontSize: '9px', fontWeight: 500, color: 'var(--gold)',
                  background: 'var(--gold-dim)', border: '1px solid var(--gold-glow)',
                  padding: '1px 6px', borderRadius: 'var(--r4)',
                }}>
                  T+1
                </span>
              )}
            </div>
            <div style={{
              fontFamily: 'DM Mono, monospace', fontSize: '13px', color: 'var(--text2)',
            }}>
              {pos.quantity}
            </div>
            <div style={{
              fontFamily: 'DM Mono, monospace', fontSize: '13px', color: 'var(--text2)',
            }}>
              ₹{pos.avg_price?.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
            </div>
            <div style={{
              fontFamily: 'DM Mono, monospace', fontSize: '13px',
              color: liveData ? 'var(--text)' : 'var(--text2)',
              display: 'flex', alignItems: 'center', gap: '4px',
              transition: 'color 0.2s',
            }}>
              ₹{currentPrice?.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
              {liveData && (
                <span style={{
                  display: 'inline-block', width: '5px', height: '5px',
                  borderRadius: '50%', background: 'var(--up)',
                  animation: 'pulse 2s infinite',
                }} />
              )}
            </div>
            <div style={{
              fontFamily: 'DM Mono, monospace', fontSize: '13px',
              color: isUp ? 'var(--up)' : 'var(--dn)',
              display: 'flex', alignItems: 'center', gap: '4px',
            }}>
              <span style={{ fontSize: '10px' }}>{isUp ? '▲' : '▼'}</span>
              {isUp ? '+' : ''}₹{Math.round(pnl).toLocaleString('en-IN')}
              <span style={{ fontSize: '10px', opacity: 0.7 }}>
                ({pnlPct.toFixed(1)}%)
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
