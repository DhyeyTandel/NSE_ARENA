// screens/Dashboard.jsx
import { useState, useEffect, useMemo } from 'react';
import { KpiCard } from '../components/KpiCard';
import { TradingViewChart } from '../components/TradingViewChart';
import { OrderPanel } from '../components/OrderPanel';
import { PositionsTable } from '../components/PositionsTable';
import { useWebSocket } from '../hooks/useWebSocket';
import { usePortfolio } from '../hooks/usePortfolio';

const DEMO_POSITIONS = [
  { ticker: 'RELIANCE', quantity: 10, avg_price: 2847.30, current_price: 2891.45, state: 'confirmed' },
  { ticker: 'TCS', quantity: 5, avg_price: 3920.00, current_price: 3885.60, state: 'confirmed' },
  { ticker: 'INFY', quantity: 15, avg_price: 1520.75, current_price: 1548.20, state: 'pending' },
];

const WS_URL = 'ws://localhost:8000/ws/prices';

export function Dashboard({ token, user }) {
  const [selectedTicker, setSelectedTicker] = useState('RELIANCE');

  // Fetch real portfolio if authenticated
  const { portfolio, refetch: refetchPortfolio } = usePortfolio(token);

  // Positions: prefer real data from API, fall back to demo
  const positions = useMemo(() => {
    if (portfolio?.holdings?.length > 0) {
      return portfolio.holdings;
    }
    return DEMO_POSITIONS;
  }, [portfolio]);

  const startingCapital = portfolio?.starting_capital || 100000;

  // Live WebSocket prices
  const { prices: livePrices, connected: wsConnected } = useWebSocket(WS_URL);

  // Compute live portfolio values using WebSocket prices
  const portfolioStats = useMemo(() => {
    // If we have real portfolio data, use it as the base
    if (portfolio) {
      return {
        holdingsValue: portfolio.holdings_value,
        investedValue: startingCapital,
        todayPnl: portfolio.total_return,
        totalValue: portfolio.total_value,
        returnPct: portfolio.total_return_pct,
        cashBalance: portfolio.cash_balance,
      };
    }

    // Fallback: compute from demo positions + live prices
    let holdingsValue = 0;
    let investedValue = 0;

    for (const pos of positions) {
      const livePrice = livePrices[pos.ticker]?.price || pos.current_price;
      holdingsValue += livePrice * pos.quantity;
      investedValue += pos.avg_price * pos.quantity;
    }

    const todayPnl = holdingsValue - investedValue;
    const totalValue = startingCapital + todayPnl;
    const returnPct = ((totalValue - startingCapital) / startingCapital * 100);

    return { holdingsValue, investedValue, todayPnl, totalValue, returnPct, cashBalance: startingCapital };
  }, [positions, livePrices, portfolio, startingCapital]);

  // Get live price for selected ticker
  const selectedLivePrice = livePrices[selectedTicker];
  const displayPrice = selectedLivePrice?.price || 2891.45;
  const displayChangePct = selectedLivePrice?.change_pct || 1.55;

  const handleSubmit = async (order) => {
    if (!token) return;
    try {
      const response = await fetch('http://localhost:8000/trades', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify(order),
      });
      if (response.ok) {
        const result = await response.json();
        console.log('Trade executed:', result);
        // Refresh portfolio after trade
        refetchPortfolio();
      } else {
        const err = await response.json();
        alert(err.detail || 'Trade failed');
      }
    } catch {
      console.log('Trade submitted (demo mode)');
    }
  };

  return (
    <div>
      {/* KPI Bar */}
      <div style={{
        display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr',
        borderBottom: '1px solid var(--border)',
      }}>
        <KpiCard
          label="Portfolio value"
          value={`₹${Math.round(portfolioStats.totalValue).toLocaleString('en-IN')}`}
          sub={`₹${Math.round(portfolioStats.cashBalance || startingCapital).toLocaleString('en-IN')} cash`}
          variant="default"
        />
        <KpiCard
          label="Today's P&L"
          value={`${portfolioStats.todayPnl >= 0 ? '+' : ''}₹${Math.round(portfolioStats.todayPnl).toLocaleString('en-IN')}`}
          sub={`${portfolioStats.returnPct >= 0 ? '+' : ''}${portfolioStats.returnPct.toFixed(1)}%`}
          variant={portfolioStats.todayPnl >= 0 ? 'up' : 'down'}
        />
        <KpiCard
          label="Trader score"
          value="300"
          sub="Beginner"
          variant="gold"
        />
        <KpiCard
          label="Season rank"
          value="—"
          sub={user ? user.username : 'demo'}
          variant="default"
        />
      </div>

      {/* Main content: Chart + Order Panel */}
      <div style={{
        display: 'grid', gridTemplateColumns: '1fr 320px',
        borderBottom: '1px solid var(--border)',
      }}>
        {/* Chart area */}
        <div style={{ padding: '18px 20px', borderRight: '1px solid var(--border)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '12px' }}>
            <div style={{
              fontSize: '16px', fontWeight: 500, letterSpacing: '-0.3px'
            }}>
              {selectedTicker}
            </div>
            <div style={{
              fontFamily: 'DM Mono, monospace', fontSize: '14px',
              fontWeight: 300, color: displayChangePct >= 0 ? 'var(--up)' : 'var(--dn)'
            }}>
              ₹{displayPrice.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
            </div>
            <div style={{
              fontFamily: 'DM Mono, monospace', fontSize: '11px',
              color: displayChangePct >= 0 ? 'var(--up)' : 'var(--dn)'
            }}>
              {displayChangePct >= 0 ? '+' : ''}{displayChangePct.toFixed(2)}%
            </div>

            {/* WebSocket connection indicator */}
            <div style={{
              display: 'flex', alignItems: 'center', gap: '4px',
              fontSize: '9px', color: wsConnected ? 'var(--up)' : 'var(--text3)',
              letterSpacing: '.04em', textTransform: 'uppercase',
            }}>
              <span style={{
                width: '5px', height: '5px', borderRadius: '50%',
                background: wsConnected ? 'var(--up)' : 'var(--dn)',
                animation: wsConnected ? 'pulse 2s infinite' : 'none',
              }} />
              {wsConnected ? 'live' : 'offline'}
            </div>

            <div style={{ display: 'flex', gap: '4px', marginLeft: 'auto' }}>
              {['1D', '1W', '1M', '3M'].map(tf => (
                <button key={tf} style={{
                  padding: '3px 8px', fontSize: '10px',
                  color: tf === '1M' ? 'var(--text)' : 'var(--text3)',
                  background: tf === '1M' ? 'var(--ink3)' : 'none',
                  border: 'none', borderRadius: 'var(--r)',
                  fontFamily: 'DM Mono, monospace', cursor: 'pointer'
                }}>
                  {tf}
                </button>
              ))}
            </div>
          </div>
          <TradingViewChart key={selectedTicker} symbol={selectedTicker} height={360} />
        </div>

        {/* Order Panel */}
        <div style={{ background: 'var(--ink2)' }}>
          <OrderPanel
            defaultSymbol={selectedTicker}
            onSubmit={handleSubmit}
            livePrice={displayPrice}
            authenticated={!!token}
          />
        </div>
      </div>

      {/* Positions — pass live prices */}
      <PositionsTable positions={positions} livePrices={livePrices} />
    </div>
  );
}
