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
        animation: 'fadeIn 0.4s var(--ease-swift)',
      }}>
        <div style={{
          width: '48px', height: '48px', borderRadius: '50%',
          background: 'var(--paper-lift)', border: '1px solid var(--faint)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: '20px', color: 'var(--muted)',
        }}>
          ▢
        </div>
        <div style={{ fontSize: '13px', color: 'var(--body-color)', fontWeight: 500 }}>
          No open positions
        </div>
        <div style={{ fontSize: '12px', color: 'var(--muted)', textAlign: 'center' }}>
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
        <div className="t-label">
          Open positions
        </div>
        <div style={{
          fontSize: '10px', fontWeight: 600,
          color: 'var(--body-color)', background: 'var(--paper-lift)',
          padding: '2px 8px', borderRadius: 'var(--r-pill)',
          fontFamily: '"JetBrains Mono", monospace',
        }}>
          {positions.length}
        </div>
      </div>

      {/* Header */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: '1fr 72px 90px 90px 100px',
        gap: '8px', padding: '8px 12px',
        borderBottom: '1px solid var(--faint)',
        borderRadius: 'var(--r-input) var(--r-input) 0 0',
        background: 'var(--paper-lift)',
      }}>
        {['Symbol', 'Qty', 'Avg Price', 'LTP', 'P&L'].map(h => (
          <div key={h} className="t-label">
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
            borderBottom: '1px solid var(--faint)',
            transition: `background var(--dur) var(--ease-swift)`,
            background: flash === 'up' ? 'var(--success-soft)'
              : flash === 'down' ? 'var(--error-soft)' : 'transparent',
            animation: `fadeInUp 0.3s var(--ease-swift) ${i * 0.05}s both`,
            cursor: 'default',
          }}
            onMouseEnter={e => {
              if (!flash) e.currentTarget.style.background = 'var(--paper-lift)';
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
                  fontSize: '9px', fontWeight: 500, color: 'var(--accent)',
                  background: 'var(--accent-soft)', border: '1px solid var(--accent-glow)',
                  padding: '1px 6px', borderRadius: 'var(--r-pill)',
                }}>
                  T+1
                </span>
              )}
            </div>
            <div style={{
              fontFamily: '"JetBrains Mono", monospace', fontSize: '13px', color: 'var(--body-color)',
            }}>
              {pos.quantity}
            </div>
            <div style={{
              fontFamily: '"JetBrains Mono", monospace', fontSize: '13px', color: 'var(--body-color)',
            }}>
              ₹{pos.avg_price?.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
            </div>
            <div style={{
              fontFamily: '"JetBrains Mono", monospace', fontSize: '13px',
              color: liveData ? 'var(--ink)' : 'var(--body-color)',
              display: 'flex', alignItems: 'center', gap: '4px',
              transition: `color var(--dur-fast) var(--ease-swift)`,
            }}>
              ₹{currentPrice?.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
              {liveData && (
                <span style={{
                  display: 'inline-block', width: '5px', height: '5px',
                  borderRadius: '50%', background: 'var(--success)',
                  animation: 'pulse 2s infinite',
                }} />
              )}
            </div>
            <div style={{
              fontFamily: '"JetBrains Mono", monospace', fontSize: '13px',
              color: isUp ? 'var(--success)' : 'var(--error)',
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
