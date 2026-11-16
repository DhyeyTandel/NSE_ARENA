// components/PositionsTable.jsx
import { useState, useEffect, useRef } from 'react';

function SkeletonRows() {
  return (
    <div className="pos-skel" aria-hidden="true">
      {[0, 1, 2].map(i => (
        <div key={i} className="pos-skel-row">
          <span className="skel" style={{ '--w': '90px' }} />
          <span className="skel" style={{ '--w': '40px' }} />
          <span className="skel" style={{ '--w': '70px' }} />
          <span className="skel" style={{ '--w': '70px' }} />
          <span className="skel" style={{ '--w': '60px' }} />
        </div>
      ))}
    </div>
  );
}

export function PositionsTable({ positions, livePrices = {}, loading = false }) {
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

  if (loading) {
    return (
      <div>
        <div className="panel-head"><h3 className="panel-title">Open positions</h3></div>
        <SkeletonRows />
      </div>
    );
  }

  if (!positions || positions.length === 0) {
    return (
      <div>
        <div className="panel-head"><h3 className="panel-title">Open positions</h3></div>
        <div className="empty">
          <svg className="empty-icon" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M4 7h16v12H4zM9 7V5h6v2M4 12h16" />
          </svg>
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
          {positions.length} {positions.length === 1 ? 'holding' : 'holdings'} · ₹{Math.round(invested).toLocaleString('en-IN')} invested
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
                <tr key={i} className={flash ? `pos-flash-${flash}` : undefined}>
                  <td>
                    <span className="pos-sym">{pos.ticker}</span>{' '}
                    <span className={`chip${pos.state === 'pending' ? ' chip--sell' : ''}`}>
                      {pos.state === 'pending' ? 'T+1' : pos.state}
                    </span>
                  </td>
                  <td className="r">{pos.quantity}</td>
                  <td className="r">{money(pos.avg_price)}</td>
                  <td className="r">{money(currentPrice)}</td>
                  <td className={`r pos-pnl ${cls}`}>
                    {pnl >= 0 ? '+' : '−'}₹{Math.abs(Math.round(pnl)).toLocaleString('en-IN')}
                  </td>
                  <td className={`r ${cls}`}>{pnl >= 0 ? '+' : '−'}{Math.abs(pnlPct).toFixed(2)}%</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
