// screens/Dashboard.jsx
import { useState, useMemo } from 'react';
import { TradingViewChart } from '../components/TradingViewChart';
import { OrderPanel } from '../components/OrderPanel';
import { PositionsTable } from '../components/PositionsTable';
import { useWebSocket } from '../hooks/useWebSocket';
import { usePortfolio } from '../hooks/usePortfolio';
import { API_URL, WS_URL } from '../config';

const DEMO_POSITIONS = [
  { ticker: 'RELIANCE', quantity: 10, avg_price: 2847.30, current_price: 2891.45, state: 'confirmed' },
  { ticker: 'TCS', quantity: 5, avg_price: 3920.00, current_price: 3885.60, state: 'confirmed' },
  { ticker: 'INFY', quantity: 15, avg_price: 1520.75, current_price: 1548.20, state: 'pending' },
];

const WATCHLIST = [
  { ticker: 'RELIANCE', chg: '+1.55%' },
  { ticker: 'TCS', chg: '−0.88%' },
  { ticker: 'INFY', chg: '+1.81%' },
  { ticker: 'HDFCBANK', chg: '+0.42%' },
  { ticker: 'TATAMOTORS', chg: '−1.12%' },
];

function getGreeting() {
  const h = new Date().getHours();
  if (h < 12) return 'Good morning';
  if (h < 17) return 'Good afternoon';
  return 'Good evening';
}

export function Dashboard({ authenticated, user }) {
  const [selectedTicker, setSelectedTicker] = useState('RELIANCE');
  const { portfolio, refetch: refetchPortfolio } = usePortfolio(authenticated);
  const { prices: livePrices, connected: wsConnected } = useWebSocket(WS_URL, authenticated);

  const positions = useMemo(() => {
    if (portfolio?.holdings?.length > 0) return portfolio.holdings;
    return DEMO_POSITIONS;
  }, [portfolio]);

  const startingCapital = portfolio?.starting_capital || 100000;

  const stats = useMemo(() => {
    if (portfolio) {
      return {
        totalValue: portfolio.total_value,
        pnl: portfolio.total_return,
        pnlPct: portfolio.total_return_pct,
        cashBalance: portfolio.cash_balance,
      };
    }
    let holdingsValue = 0, investedValue = 0;
    for (const pos of positions) {
      const livePrice = livePrices[pos.ticker]?.price || pos.current_price;
      holdingsValue += livePrice * pos.quantity;
      investedValue += pos.avg_price * pos.quantity;
    }
    const pnl = holdingsValue - investedValue;
    const totalValue = startingCapital + pnl;
    const pnlPct = (totalValue - startingCapital) / startingCapital * 100;
    return { totalValue, pnl, pnlPct, cashBalance: startingCapital };
  }, [positions, livePrices, portfolio, startingCapital]);

  const selectedLivePrice = livePrices[selectedTicker];
  const displayPrice = selectedLivePrice?.price || 2891.45;
  const displayChangePct = selectedLivePrice?.change_pct || 1.55;

  const handleSubmit = async (order) => {
    if (!authenticated) return;
    try {
      const response = await fetch(`${API_URL}/trades`, {
        method: 'POST', credentials: 'include',
        headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
        body: JSON.stringify(order),
      });
      if (response.ok) refetchPortfolio();
      else { const err = await response.json(); alert(err.detail || 'Trade failed'); }
    } catch { alert('Network error — trade not submitted.'); }
  };

  const inr = n => '₹' + Math.round(n).toLocaleString('en-IN');
  const today = new Date().toLocaleDateString('en-IN', { weekday: 'long', day: 'numeric', month: 'long' });
  const pnlUp = stats.pnl >= 0;

  return (
    <div style={{ animation: 'fadeIn 0.3s var(--ease-swift)' }}>
      {/* Season ink band */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: '28px',
        padding: '12px 32px',
        background: 'var(--ink-surface)', color: 'var(--on-ink)',
      }}>
        <div className="t-eyebrow" style={{ color: 'var(--on-ink-muted)' }}>
          Season 4 · Monsoon
        </div>
        <div style={{ fontSize: '14px', color: 'var(--on-ink-muted)' }}>
          Ends in <strong style={{ color: 'var(--on-ink)' }}>12 days</strong>
        </div>
        <div style={{ fontSize: '14px', color: 'var(--on-ink-muted)' }}>
          Your rank <strong style={{ color: 'var(--on-ink)' }}>#23</strong>{' '}
          <span style={{ color: '#4ADE80' }}>▲2 today</span>
        </div>
        <div style={{ fontSize: '14px', color: 'var(--on-ink-muted)' }}>
          1,204 traders competing
        </div>
      </div>

      <div style={{ maxWidth: '1360px', margin: '0 auto', padding: '24px 32px 40px' }}>
        {/* Greeting */}
        <div style={{
          display: 'flex', alignItems: 'baseline', gap: '12px', marginBottom: '18px',
          animation: 'fadeInUp 0.4s var(--ease-swift)',
        }}>
          <div className="t-display" style={{ fontSize: '28px' }}>
            {getGreeting()}, <em>{user?.username || 'Trader'}</em>
          </div>
          <div style={{ fontSize: '13px', color: 'var(--muted)' }}>{today}</div>
        </div>

        {/* KPI strip */}
        <div style={{
          display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)',
          background: 'var(--card)', border: '1px solid var(--faint)',
          borderRadius: 'var(--r-card)', overflow: 'hidden', marginBottom: '16px',
        }}>
          <div style={{ padding: '18px 22px', borderRight: '1px solid var(--faint)' }}>
            <div className="t-label" style={{ marginBottom: '8px' }}>Portfolio value</div>
            <div className="t-kpi" style={{ fontSize: '24px' }}>{inr(stats.totalValue)}</div>
            <div style={{ fontSize: '13px', color: 'var(--muted)', marginTop: '4px' }}>
              {inr(stats.cashBalance)} in cash
            </div>
          </div>
          <div style={{ padding: '18px 22px', borderRight: '1px solid var(--faint)' }}>
            <div className="t-label" style={{ marginBottom: '8px' }}>Season P&L</div>
            <div className="t-kpi" style={{ fontSize: '24px', color: pnlUp ? 'var(--success)' : 'var(--error)' }}>
              {pnlUp ? '+' : '−'}{inr(Math.abs(stats.pnl))}
            </div>
            <div style={{ fontSize: '13px', color: pnlUp ? 'var(--success)' : 'var(--error)', marginTop: '4px' }}>
              {pnlUp ? '+' : ''}{stats.pnlPct.toFixed(1)}% on ₹1L capital
            </div>
          </div>
          <div style={{ padding: '18px 22px', borderRight: '1px solid var(--faint)' }}>
            <div className="t-label" style={{ marginBottom: '8px' }}>Trader score</div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: '10px' }}>
              <div className="t-kpi" style={{ fontSize: '24px' }}>412</div>
              <div style={{
                fontSize: '12.5px', fontWeight: 560, padding: '2px 10px',
                borderRadius: '999px', background: 'var(--accent-soft)', color: 'var(--accent-deep)',
              }}>Consistent</div>
            </div>
            <div style={{
              height: '4px', background: 'var(--faint-soft)', borderRadius: '999px',
              marginTop: '10px', overflow: 'hidden',
            }}>
              <div style={{ width: '41%', height: '100%', background: 'var(--accent)', borderRadius: '999px' }} />
            </div>
          </div>
          <div style={{ padding: '18px 22px' }}>
            <div className="t-label" style={{ marginBottom: '8px' }}>Season rank</div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: '10px' }}>
              <div className="t-kpi" style={{ fontSize: '24px' }}>#23</div>
              <div style={{ fontSize: '13px', color: 'var(--success)', fontWeight: 560 }}>▲2</div>
            </div>
            <div style={{ fontSize: '13px', color: 'var(--muted)', marginTop: '4px' }}>
              ₹1,840 behind #22
            </div>
          </div>
        </div>

        {/* Chart + Order panel */}
        <div style={{
          display: 'grid', gridTemplateColumns: '1fr 336px',
          background: 'var(--card)', border: '1px solid var(--faint)',
          borderRadius: 'var(--r-card)', overflow: 'hidden', marginBottom: '16px',
        }}>
          {/* Chart */}
          <div style={{ padding: '20px 24px', borderRight: '1px solid var(--faint)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '14px', marginBottom: '6px' }}>
              <div className="t-title" style={{ fontSize: '24px' }}>{selectedTicker}</div>
              <div className="t-mono" style={{ color: 'var(--muted)' }}>NSE : {selectedTicker}</div>
              <div style={{
                marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '6px',
              }}>
                <span style={{
                  width: '6px', height: '6px', borderRadius: '999px',
                  background: wsConnected ? 'var(--success)' : 'var(--error)',
                  animation: wsConnected ? 'pulse 2s infinite' : 'none',
                }} />
                <span className="t-mono-sm" style={{
                  color: wsConnected ? 'var(--success)' : 'var(--muted)',
                  textTransform: 'uppercase', letterSpacing: '.08em',
                }}>
                  {wsConnected ? 'Live' : 'Offline'}
                </span>
              </div>
            </div>
            <div style={{
              display: 'flex', alignItems: 'baseline', gap: '12px', marginBottom: '14px',
            }}>
              <div className="t-kpi" style={{ fontSize: '20px' }}>
                ₹{displayPrice.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
              </div>
              <div className="t-mono" style={{
                color: displayChangePct >= 0 ? 'var(--success)' : 'var(--error)',
                fontWeight: 500,
              }}>
                {displayChangePct >= 0 ? '+' : ''}{displayChangePct.toFixed(2)}%
              </div>
            </div>
            <TradingViewChart key={selectedTicker} symbol={selectedTicker} height={380} />
            {/* Watchlist pills */}
            <div style={{ display: 'flex', gap: '8px', marginTop: '12px', flexWrap: 'wrap' }}>
              {WATCHLIST.map((w) => {
                const isActive = w.ticker === selectedTicker;
                const isUp = w.chg[0] === '+';
                return (
                  <button key={w.ticker} onClick={() => setSelectedTicker(w.ticker)} style={{
                    border: `1px solid ${isActive ? 'var(--accent)' : 'var(--faint)'}`,
                    cursor: 'pointer',
                    background: isActive ? 'var(--accent-soft)' : 'var(--card)',
                    borderRadius: '999px', padding: '6px 14px',
                    display: 'flex', alignItems: 'baseline', gap: '8px',
                    fontFamily: '"JetBrains Mono", monospace', fontSize: '12px',
                    transition: 'all var(--dur-fast) var(--ease-swift)',
                  }}
                    onMouseEnter={e => { e.currentTarget.style.transform = 'translateY(-2px)'; }}
                    onMouseLeave={e => { e.currentTarget.style.transform = 'translateY(0)'; }}
                  >
                    <span style={{ fontWeight: 600, color: 'var(--ink)' }}>{w.ticker}</span>
                    <span style={{ color: isUp ? 'var(--success)' : 'var(--error)' }}>{w.chg}</span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Order panel */}
          <div style={{ background: 'var(--paper-lift)' }}>
            <OrderPanel
              defaultSymbol={selectedTicker}
              onSubmit={handleSubmit}
              livePrice={displayPrice}
              authenticated={authenticated}
            />
          </div>
        </div>

        {/* Positions */}
        <div style={{
          background: 'var(--card)', border: '1px solid var(--faint)',
          borderRadius: 'var(--r-card)', overflow: 'hidden',
        }}>
          <PositionsTable positions={positions} livePrices={livePrices} />
        </div>
      </div>
    </div>
  );
}
