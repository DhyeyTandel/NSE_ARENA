// screens/Dashboard.jsx
import { useState, useMemo } from 'react';
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

function getGreeting() {
  const h = new Date().getHours();
  if (h < 12) return 'Good morning';
  if (h < 17) return 'Good afternoon';
  return 'Good evening';
}

export function Dashboard({ token, user }) {
  const [selectedTicker, setSelectedTicker] = useState('RELIANCE');
  const { portfolio, refetch: refetchPortfolio } = usePortfolio(token);

  const positions = useMemo(() => {
    if (portfolio?.holdings?.length > 0) return portfolio.holdings;
    return DEMO_POSITIONS;
  }, [portfolio]);

  const startingCapital = portfolio?.starting_capital || 100000;
  const { prices: livePrices, connected: wsConnected } = useWebSocket(WS_URL, token);

  const portfolioStats = useMemo(() => {
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

  const selectedLivePrice = livePrices[selectedTicker];
  const displayPrice = selectedLivePrice?.price || 2891.45;
  const displayChangePct = selectedLivePrice?.change_pct || 1.55;

  const handleSubmit = async (order) => {
    if (!token) return;
    try {
      const response = await fetch('http://localhost:8000/trades', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify(order),
      });
      if (response.ok) {
        refetchPortfolio();
      } else {
        const err = await response.json();
        alert(err.detail || 'Trade failed');
      }
    } catch {
      console.log('Trade submitted (demo mode)');
    }
  };

  const today = new Date().toLocaleDateString('en-IN', { weekday: 'long', day: 'numeric', month: 'long' });

  return (
    <div style={{ animation: 'fadeIn 0.3s var(--ease)' }}>
      {/* Greeting */}
      <div style={{
        padding: '20px 24px 0',
        display: 'flex', alignItems: 'baseline', gap: '8px',
        animation: 'fadeInUp 0.4s var(--ease)',
      }}>
        <div style={{ fontSize: '18px', fontWeight: 600, letterSpacing: '-0.3px' }}>
          {getGreeting()}, <span style={{ color: 'var(--gold)' }}>{user?.username || 'Trader'}</span>
        </div>
        <div style={{ fontSize: '12px', color: 'var(--text3)', marginLeft: '4px' }}>
          {today}
        </div>
      </div>

      {/* KPI Bar */}
      <div style={{
        display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)',
        margin: '16px 24px 0',
        background: 'var(--ink2)',
        border: '1px solid var(--border2)',
        borderRadius: 'var(--r2)',
        overflow: 'hidden',
      }}>
        <KpiCard
          label="Portfolio value"
          value={`₹${Math.round(portfolioStats.totalValue).toLocaleString('en-IN')}`}
          sub={`₹${Math.round(portfolioStats.cashBalance || startingCapital).toLocaleString('en-IN')} cash`}
          variant="default" icon="portfolio" delay={0}
        />
        <KpiCard
          label="Today's P&L"
          value={`${portfolioStats.todayPnl >= 0 ? '+' : ''}₹${Math.round(portfolioStats.todayPnl).toLocaleString('en-IN')}`}
          sub={`${portfolioStats.returnPct >= 0 ? '+' : ''}${portfolioStats.returnPct.toFixed(1)}%`}
          variant={portfolioStats.todayPnl >= 0 ? 'up' : 'down'}
          icon="pnl" delay={0.05}
        />
        <KpiCard
          label="Trader score"
          value="300"
          sub="Beginner"
          variant="gold" icon="score" delay={0.1}
        />
        <KpiCard
          label="Season rank"
          value="—"
          sub={user ? user.username : 'demo'}
          variant="default" icon="rank" delay={0.15}
        />
      </div>

      {/* Main content: Chart + Order Panel */}
      <div style={{
        display: 'grid', gridTemplateColumns: '1fr 340px',
        margin: '16px 24px 0',
        background: 'var(--ink2)',
        border: '1px solid var(--border2)',
        borderRadius: 'var(--r2)',
        overflow: 'hidden',
        animation: 'fadeInUp 0.5s var(--ease) 0.1s both',
      }}>
        {/* Chart area */}
        <div style={{ padding: '20px 22px', borderRight: '1px solid var(--border2)' }}>
          {/* Ticker header */}
          <div style={{
            display: 'flex', alignItems: 'center', gap: '14px', marginBottom: '16px',
          }}>
            <div style={{ fontSize: '20px', fontWeight: 700, letterSpacing: '-0.4px' }}>
              {selectedTicker}
            </div>
            <div style={{
              fontFamily: 'DM Mono, monospace', fontSize: '16px',
              fontWeight: 400,
              color: displayChangePct >= 0 ? 'var(--up)' : 'var(--dn)',
            }}>
              ₹{displayPrice.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
            </div>
            <div style={{
              fontFamily: 'DM Mono, monospace', fontSize: '12px',
              padding: '3px 8px', borderRadius: 'var(--r4)',
              background: displayChangePct >= 0 ? 'var(--up-dim)' : 'var(--dn-dim)',
              color: displayChangePct >= 0 ? 'var(--up)' : 'var(--dn)',
              fontWeight: 500,
            }}>
              {displayChangePct >= 0 ? '+' : ''}{displayChangePct.toFixed(2)}%
            </div>

            {/* WebSocket indicator */}
            <div style={{
              display: 'flex', alignItems: 'center', gap: '5px',
              fontSize: '10px', fontWeight: 500,
              color: wsConnected ? 'var(--up)' : 'var(--text3)',
              letterSpacing: '.06em', textTransform: 'uppercase',
              marginLeft: 'auto',
            }}>
              <span style={{
                width: '6px', height: '6px', borderRadius: '50%',
                background: wsConnected ? 'var(--up)' : 'var(--dn)',
                animation: wsConnected ? 'pulse 2s infinite' : 'none',
                boxShadow: wsConnected ? '0 0 6px var(--up)' : 'none',
              }} />
              {wsConnected ? 'Live' : 'Offline'}
            </div>
          </div>

          <TradingViewChart key={selectedTicker} symbol={selectedTicker} height={380} />
        </div>

        {/* Order Panel */}
        <div style={{ background: 'var(--ink)' }}>
          <OrderPanel
            defaultSymbol={selectedTicker}
            onSubmit={handleSubmit}
            livePrice={displayPrice}
            authenticated={!!token}
          />
        </div>
      </div>

      {/* Positions */}
      <div style={{
        margin: '16px 24px 24px',
        background: 'var(--ink2)',
        border: '1px solid var(--border2)',
        borderRadius: 'var(--r2)',
        overflow: 'hidden',
        animation: 'fadeInUp 0.5s var(--ease) 0.2s both',
      }}>
        <PositionsTable positions={positions} livePrices={livePrices} />
      </div>
    </div>
  );
}
