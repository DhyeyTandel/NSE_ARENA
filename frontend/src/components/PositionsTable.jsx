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

    // Update previous prices
    const updated = {};
    for (const [ticker, data] of Object.entries(livePrices)) {
      updated[ticker] = data.price;
    }
    prevPrices.current = updated;
  }, [livePrices]);

  if (!positions || positions.length === 0) {
    return (
      <div style={{ padding: '18px 20px', color: 'var(--text3)', fontSize: '12px' }}>
        No open positions
      </div>
    );
  }

  return (
    <div style={{ padding: '0 20px 18px' }}>
      <div style={{
        fontSize: '10px', fontWeight: 400, color: 'var(--text3)',
        textTransform: 'uppercase', letterSpacing: '.06em',
        marginBottom: '10px', paddingTop: '14px'
      }}>
        Open positions
      </div>

      {/* Header */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: '1fr 72px 80px 80px 80px',
        gap: '8px', padding: '6px 0',
        borderBottom: '1px solid var(--border)',
      }}>
        {['Symbol', 'Qty', 'Avg Price', 'LTP', 'P&L'].map(h => (
          <div key={h} style={{
            fontSize: '10px', color: 'var(--text3)',
            textTransform: 'uppercase', letterSpacing: '.06em'
          }}>
            {h}
          </div>
        ))}
      </div>

      {/* Rows */}
      {positions.map((pos, i) => {
        // Use live price if available, fall back to position's current_price
        const liveData = livePrices[pos.ticker];
        const currentPrice = liveData?.price || pos.current_price;
        const pnl = (currentPrice - pos.avg_price) * pos.quantity;
        const pnlPct = pos.avg_price > 0 ? ((currentPrice - pos.avg_price) / pos.avg_price * 100) : 0;
        const isUp = pnl >= 0;
        const flash = flashTickers[pos.ticker];

        return (
          <div key={i} style={{
            display: 'grid',
            gridTemplateColumns: '1fr 72px 80px 80px 80px',
            gap: '8px', padding: '8px 0',
            borderBottom: '1px solid var(--border)',
            transition: 'background .3s',
            background: flash === 'up' ? 'var(--up-dim)' : flash === 'down' ? 'var(--dn-dim)' : 'none',
          }}>
            <div style={{ fontSize: '12px', fontWeight: 500 }}>
              {pos.ticker}
              {pos.state === 'pending' && (
                <span style={{
                  fontSize: '9px', color: 'var(--gold)',
                  background: 'var(--gold-dim)', border: '1px solid var(--gold-glow)',
                  padding: '1px 5px', borderRadius: '2px', marginLeft: '6px'
                }}>
                  T+1
                </span>
              )}
            </div>
            <div style={{ fontFamily: 'DM Mono, monospace', fontSize: '12px', color: 'var(--text2)' }}>
              {pos.quantity}
            </div>
            <div style={{ fontFamily: 'DM Mono, monospace', fontSize: '12px', color: 'var(--text2)' }}>
              ₹{pos.avg_price?.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
            </div>
            <div style={{
              fontFamily: 'DM Mono, monospace', fontSize: '12px',
              color: liveData ? 'var(--text)' : 'var(--text2)',
              transition: 'color .2s'
            }}>
              ₹{currentPrice?.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
              {liveData && (
                <span style={{
                  display: 'inline-block', width: '4px', height: '4px',
                  borderRadius: '50%', background: 'var(--up)',
                  marginLeft: '4px', verticalAlign: 'middle',
                  animation: 'pulse 2s infinite'
                }} />
              )}
            </div>
            <div style={{
              fontFamily: 'DM Mono, monospace', fontSize: '12px',
              color: isUp ? 'var(--up)' : 'var(--dn)'
            }}>
              {isUp ? '+' : ''}₹{Math.round(pnl).toLocaleString('en-IN')}
              <span style={{ fontSize: '10px', marginLeft: '4px' }}>
                ({pnlPct.toFixed(1)}%)
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
