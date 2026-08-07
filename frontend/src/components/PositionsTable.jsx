// components/PositionsTable.jsx
import { useState, useEffect, useRef } from 'react';

export function PositionsTable({ positions, livePrices = {} }) {
  const [flashTickers, setFlashTickers] = useState({});
  const prevPrices = useRef({});

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
    for (const [ticker, data] of Object.entries(livePrices)) updated[ticker] = data.price;
    prevPrices.current = updated;
  }, [livePrices]);

  if (!positions || positions.length === 0) {
    return (
      <div style={{
        padding: '32px 24px', display: 'flex', flexDirection: 'column',
        alignItems: 'center', gap: '10px',
      }}>
        <div style={{ fontSize: '18px', color: 'var(--muted)' }}>▢</div>
        <div style={{ fontSize: '13px', fontWeight: 500, color: 'var(--body-color)' }}>No open positions</div>
        <div style={{ fontSize: '12px', color: 'var(--muted)', textAlign: 'center' }}>
          Place your first trade using the order panel above
        </div>
      </div>
    );
  }

  const invested = positions.reduce((s, p) => s + p.avg_price * p.quantity, 0);

  return (
    <div>
      {/* Header */}
      <div style={{
        display: 'flex', alignItems: 'baseline', gap: '12px',
        padding: '16px 22px', borderBottom: '1px solid var(--faint)',
      }}>
        <div className="t-title" style={{ fontSize: '19px' }}>Open positions</div>
        <div style={{ fontSize: '13px', color: 'var(--muted)' }}>
          {positions.length} holdings · ₹{Math.round(invested).toLocaleString('en-IN')} invested
        </div>
      </div>

      {/* Column headers */}
      <div style={{
        display: 'grid', gridTemplateColumns: '1.4fr 1fr 1fr 1fr 1fr 1fr',
        padding: '10px 22px', borderBottom: '1px solid var(--faint-soft)',
        fontFamily: '"JetBrains Mono", monospace',
        fontSize: '10.5px', fontWeight: 600, letterSpacing: '.12em',
        textTransform: 'uppercase', color: 'var(--muted-soft)',
      }}>
        <div>Instrument</div>
        <div style={{ textAlign: 'right' }}>Qty</div>
        <div style={{ textAlign: 'right' }}>Avg price</div>
        <div style={{ textAlign: 'right' }}>LTP</div>
        <div style={{ textAlign: 'right' }}>P&L</div>
        <div style={{ textAlign: 'right' }}>Change</div>
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
            display: 'grid', gridTemplateColumns: '1.4fr 1fr 1fr 1fr 1fr 1fr',
            padding: '13px 22px', borderBottom: '1px solid var(--faint-soft)',
            fontSize: '14px', alignItems: 'baseline',
            background: flash === 'up' ? 'var(--success-soft)' : flash === 'down' ? 'var(--error-soft)' : 'transparent',
            transition: 'background var(--dur) var(--ease-swift)',
            cursor: 'default',
          }}
            onMouseEnter={e => { if (!flash) e.currentTarget.style.background = 'var(--paper-lift)'; }}
            onMouseLeave={e => { if (!flash) e.currentTarget.style.background = 'transparent'; }}
          >
            <div style={{ display: 'flex', alignItems: 'baseline', gap: '10px' }}>
              <span style={{ fontWeight: 600 }}>{pos.ticker}</span>
              <span style={{
                fontSize: '11.5px', padding: '1px 8px', borderRadius: '999px',
                fontWeight: 560,
                background: pos.state === 'pending' ? 'var(--accent-soft)' : 'var(--faint-soft)',
                color: pos.state === 'pending' ? 'var(--accent-deep)' : 'var(--muted)',
              }}>{pos.state === 'pending' ? 'T+1' : pos.state}</span>
            </div>
            <div style={{ textAlign: 'right', fontFamily: '"JetBrains Mono", monospace' }}>{pos.quantity}</div>
            <div style={{ textAlign: 'right', fontFamily: '"JetBrains Mono", monospace' }}>
              ₹{pos.avg_price?.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
            </div>
            <div style={{ textAlign: 'right', fontFamily: '"JetBrains Mono", monospace' }}>
              ₹{currentPrice?.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
            </div>
            <div style={{
              textAlign: 'right', fontFamily: '"JetBrains Mono", monospace',
              fontWeight: 500, color: isUp ? 'var(--success)' : 'var(--error)',
            }}>
              {isUp ? '+' : '−'}₹{Math.abs(Math.round(pnl)).toLocaleString('en-IN')}
            </div>
            <div style={{
              textAlign: 'right', fontFamily: '"JetBrains Mono", monospace',
              color: isUp ? 'var(--success)' : 'var(--error)',
            }}>
              {isUp ? '+' : ''}{pnlPct.toFixed(2)}%
            </div>
          </div>
        );
      })}
    </div>
  );
}
