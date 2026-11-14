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
      <div>
        <div className="panel-head"><h3 className="panel-title">Open positions</h3></div>
        <div className="empty">
          <strong>No open positions</strong>
          Place your first trade using the order panel
        </div>
      </div>
    );
  }

  const invested = positions.reduce((s, p) => s + p.avg_price * p.quantity, 0);
  const money = n => '₹' + n?.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

  return (
    <div>
      <div className="panel-head">
        <h3 className="panel-title">Open positions</h3>
        <span className="panel-sub">
          {positions.length} holdings · ₹{Math.round(invested).toLocaleString('en-IN')} invested
        </span>
      </div>
      <div className="table-wrap">
        <table className="tbl">
          <thead>
            <tr>
              <th>Instrument</th>
              <th className="r">Qty</th>
              <th className="r">Avg price</th>
              <th className="r">LTP</th>
              <th className="r">P&L</th>
              <th className="r">Change</th>
            </tr>
          </thead>
          <tbody>
            {positions.map((pos, i) => {
              const liveData = livePrices[pos.ticker];
              const currentPrice = liveData?.price || pos.current_price;
              const pnl = (currentPrice - pos.avg_price) * pos.quantity;
              const pnlPct = pos.avg_price > 0 ? ((currentPrice - pos.avg_price) / pos.avg_price * 100) : 0;
              const cls = pnl >= 0 ? 'up' : 'dn';
              const flash = flashTickers[pos.ticker];
              return (
                <tr key={i} style={{
                  background: flash === 'up' ? 'var(--gain-bg)' : flash === 'down' ? 'var(--loss-bg)' : undefined,
                  transition: 'background 0.3s',
                }}>
                  <td>
                    <span style={{ fontWeight: 500 }}>{pos.ticker}</span>{' '}
                    <span className={`chip${pos.state === 'pending' ? ' chip--sell' : ''}`}>
                      {pos.state === 'pending' ? 'T+1' : pos.state}
                    </span>
                  </td>
                  <td className="r">{pos.quantity}</td>
                  <td className="r">{money(pos.avg_price)}</td>
                  <td className="r">{money(currentPrice)}</td>
                  <td className={`r ${cls}`} style={{ fontWeight: 500 }}>
                    {pnl >= 0 ? '+' : '−'}₹{Math.abs(Math.round(pnl)).toLocaleString('en-IN')}
                  </td>
                  <td className={`r ${cls}`}>{pnl >= 0 ? '+' : ''}{pnlPct.toFixed(2)}%</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
