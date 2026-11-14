// screens/Dashboard.jsx
import { useState, useMemo, useEffect } from 'react';
import axios from 'axios';
import { TradingViewChart } from '../components/TradingViewChart';
import { OrderPanel } from '../components/OrderPanel';
import { PositionsTable } from '../components/PositionsTable';
import { useWebSocket } from '../hooks/useWebSocket';
import { usePortfolio } from '../hooks/usePortfolio';
import { useSeasonStanding } from '../hooks/useSeasonStanding';
import { API_URL, WS_URL } from '../config';
import './Dashboard.css';

const DEMO_POSITIONS = [
  { ticker: 'RELIANCE', quantity: 10, avg_price: 2847.30, current_price: 2891.45, state: 'confirmed' },
  { ticker: 'TCS', quantity: 5, avg_price: 3920.00, current_price: 3885.60, state: 'confirmed' },
  { ticker: 'INFY', quantity: 15, avg_price: 1520.75, current_price: 1548.20, state: 'pending' },
];


export function Dashboard({ authenticated, user }) {
  const [selectedTicker, setSelectedTicker] = useState('RELIANCE');
  const [chartRange, setChartRange] = useState('1M');
  const [watchlist, setWatchlist] = useState(null); // null until /tickers answers
  const [filter, setFilter] = useState('');
  const [orderSide, setOrderSide] = useState('buy');
  const [wlOpen, setWlOpen] = useState(false); // collapsible on narrow screens only
  const { portfolio, refetch: refetchPortfolio } = usePortfolio(authenticated);
  const { prices: livePrices, connected: wsConnected } = useWebSocket(WS_URL, authenticated);

  useEffect(() => {
    let cancelled = false;
    axios.get(`${API_URL}/tickers`)
      .then(res => { if (!cancelled && Array.isArray(res.data?.tickers)) setWatchlist(res.data.tickers); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);

  // Optional Kite Connect real-time feed: only offer "Connect Kite" when the
  // backend has keys but no live session.
  const [kite, setKite] = useState(null);
  const isAdmin = !!user?.is_admin;
  const refreshKite = () => axios.get(`${API_URL}/api/kite/status`)
    .then(res => setKite(res.data))
    .catch(() => {});
  useEffect(() => {
    let cancelled = false;
    axios.get(`${API_URL}/api/kite/status`)
      .then(res => { if (!cancelled) setKite(res.data); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);
  const disconnectKite = () => axios.post(
    `${API_URL}/api/kite/disconnect`, null,
    { withCredentials: true, headers: { 'X-Requested-With': 'XMLHttpRequest' } },
  ).then(refreshKite).catch(() => {});

  // Backend list, or (if /tickers failed) whatever has ticked on the socket.
  const watchTickers = useMemo(() => {
    const list = watchlist ?? Object.keys(livePrices);
    const q = filter.trim().toUpperCase();
    return q ? list.filter(t => t.toUpperCase().includes(q)) : list;
  }, [watchlist, livePrices, filter]);

  const positions = useMemo(() => {
    // DEMO_POSITIONS is a preview for logged-out visitors only. Once
    // authenticated, always show the real holdings — even an empty
    // array — never fake positions a real trader could mistake for
    // their actual portfolio.
    if (!authenticated) return DEMO_POSITIONS;
    return portfolio?.holdings ?? [];
  }, [portfolio, authenticated]);

  const standing = useSeasonStanding(authenticated, user);

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
  const displayPrice = selectedLivePrice?.price ?? null;
  const displayChangePct = selectedLivePrice?.change_pct ?? null;

  // Badge states. "Live" only when the socket is up AND the backend says NSE
  // is open; a connected socket outside market hours is showing the last close.
  const marketOpen = Object.values(livePrices).find(p => typeof p?.market_open === 'boolean')?.market_open;
  // The selected ticker's source wins; otherwise any tick that carries one.
  const source = selectedLivePrice?.source
    ?? Object.values(livePrices).find(p => p?.source)?.source;
  const feed = !wsConnected
    ? { label: 'Offline', dot: 'var(--loss)', color: 'var(--text-2)', pulse: false }
    : marketOpen === true
      ? source === 'yahoo'
        ? { label: 'Delayed', dot: 'var(--gain)', color: 'var(--text-2)', pulse: false }
        : { label: 'Live', dot: 'var(--gain)', color: 'var(--gain-text)', pulse: true }
      : marketOpen === false
        ? { label: 'Market closed', dot: 'var(--text-2)', color: 'var(--text-2)', pulse: false }
        : { label: 'Connecting', dot: 'var(--text-2)', color: 'var(--text-2)', pulse: false };

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
  const px = n => (typeof n === 'number' ? '₹' + n.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '—');
  const pnlUp = stats.pnl >= 0;
  const signed = v => `${v >= 0 ? '+' : '−'}${Math.abs(v).toFixed(2)}%`;
  const chgClass = v => (typeof v !== 'number' ? 'muted' : v >= 0 ? 'up' : 'dn');

  const prevClose = selectedLivePrice?.previous_close;
  const absChange = typeof displayPrice === 'number' && typeof prevClose === 'number' ? displayPrice - prevClose : null;
  const keyStats = [
    ['Open', selectedLivePrice?.open, px],
    ['High', selectedLivePrice?.day_high, px],
    ['Low', selectedLivePrice?.day_low, px],
    ['Prev. close', prevClose, px],
    ['Volume', selectedLivePrice?.volume, v => (typeof v === 'number' ? v.toLocaleString('en-IN') : '—')],
  ];

  const pickTicker = (ticker, side) => {
    setSelectedTicker(ticker);
    if (side) setOrderSide(side);
  };

  return (
    <div className="dash">
      {/* Watchlist */}
      <aside className={`wl${wlOpen ? '' : ' wl--collapsed'}`} aria-label="Watchlist">
        <button type="button" className="wl-toggle" aria-expanded={wlOpen} onClick={() => setWlOpen(o => !o)}>
          <span>Watchlist</span>
          <span>{selectedTicker} · {wlOpen ? 'Hide' : 'Show'}</span>
        </button>
        <div className="wl-search">
          <input
            type="text" className="input" value={filter} onChange={e => setFilter(e.target.value)}
            placeholder="Search stocks" aria-label="Filter tickers"
          />
        </div>
        <ul className="wl-list" data-testid="watchlist" role="listbox" aria-label="Stocks">
          {watchTickers.map((ticker) => {
            const chg = livePrices[ticker]?.change_pct;
            const last = livePrices[ticker]?.price;
            const hasChg = typeof chg === 'number';
            const selected = ticker === selectedTicker;
            return (
              <li
                key={ticker} data-ticker={ticker} role="option" aria-selected={selected} tabIndex={0}
                className={`wl-row${selected ? ' is-selected' : ''}`}
                onClick={() => pickTicker(ticker)}
                onKeyDown={e => { if (e.target === e.currentTarget && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); pickTicker(ticker); } }}
              >
                <span className="wl-sym">{ticker}</span>
                <span className={`wl-chg ${hasChg ? chgClass(chg) : 'muted'}`}>{hasChg ? signed(chg) : '—'}</span>
                <span className="wl-px">{typeof last === 'number' ? last.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '—'}</span>
                <span className="wl-actions">
                  <button type="button" className="wl-b" aria-label={`Buy ${ticker}`} title="Buy"
                    onClick={e => { e.stopPropagation(); pickTicker(ticker, 'buy'); }}>B</button>
                  <button type="button" className="wl-s" aria-label={`Sell ${ticker}`} title="Sell"
                    onClick={e => { e.stopPropagation(); pickTicker(ticker, 'sell'); }}>S</button>
                </span>
              </li>
            );
          })}
        </ul>
        <div className="wl-foot">{watchTickers.length} {watchTickers.length === 1 ? 'stock' : 'stocks'}</div>
      </aside>

      {/* Content */}
      <div className="dash-main">
        <div className="stats">
          <div className="stat">
            <div className="stat-label">Portfolio value</div>
            <div className="stat-value">{inr(stats.totalValue)}</div>
            <div className="stat-sub">{inr(stats.cashBalance)} in cash</div>
          </div>
          <div className="stat">
            <div className="stat-label">Season P&L</div>
            <div className={`stat-value ${pnlUp ? 'up' : 'dn'}`}>{pnlUp ? '+' : '−'}{inr(Math.abs(stats.pnl))}</div>
            <div className={`stat-sub ${pnlUp ? 'up' : 'dn'}`}>{pnlUp ? '+' : ''}{stats.pnlPct.toFixed(1)}% on ₹1L capital</div>
          </div>
          <div className="stat">
            <div className="stat-label">Trader score</div>
            <div className="stat-value">
              {standing.score ? standing.score.final_score : '—'}
              {standing.score?.grade && <> <span className="chip chip--ai" style={{ verticalAlign: 'middle' }}>{standing.score.grade}</span></>}
            </div>
          </div>
          <div className="stat">
            <div className="stat-label">Rank</div>
            <div className="stat-value">{standing.rank != null ? `#${standing.rank}` : '—'}</div>
            {standing.gapToNext != null && (
              <div className="stat-sub">{inr(standing.gapToNext)} behind #{standing.aheadRank}</div>
            )}
          </div>
        </div>

        <div className="sv-head">
          <div>
            <div className="sv-sym">
              <h2>{selectedTicker}</h2>
              <span className="chip">NSE</span>
            </div>
            <div className="sv-price">{displayPrice != null ? px(displayPrice) : '—'}</div>
            <div className="sv-chg">
              <span className={chgClass(displayChangePct)}>
                {displayChangePct == null ? '—' : signed(displayChangePct)}
              </span>
              {absChange != null && (
                <span className={chgClass(absChange)}>{absChange >= 0 ? '+' : '−'}₹{Math.abs(absChange).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
              )}
            </div>
          </div>
          <div className="feed">
            <span className="feed-dot" style={{ background: feed.dot, animation: feed.pulse ? 'pulse 2s infinite' : 'none' }} />
            <span style={{ color: feed.color, fontWeight: 500 }}>{feed.label}</span>
            {isAdmin && kite?.configured && kite.connected && (
              <button type="button" onClick={disconnectKite} className="link-btn">Disconnect Kite</button>
            )}
            {isAdmin && kite?.configured && !kite.connected && (
              <a href={`${API_URL}/api/kite/login`} className="link-btn">Connect Kite</a>
            )}
          </div>
        </div>

        <div className="sv-grid">
          <div className="panel">
            <div className="sv-chart">
              <TradingViewChart key={selectedTicker} symbol={selectedTicker} height={360}
                range={chartRange} onRangeChange={setChartRange} />
            </div>
            <dl className="keystats keystats-wrap">
              {keyStats.map(([label, value, fmt]) => (
                <div key={label}>
                  <dt>{label}</dt>
                  <dd>{typeof value === 'number' ? fmt(value) : '—'}</dd>
                </div>
              ))}
            </dl>
          </div>

          <OrderPanel
            defaultSymbol={selectedTicker}
            onSubmit={handleSubmit}
            livePrice={displayPrice ?? 0}
            authenticated={authenticated}
            cashBalance={stats.cashBalance}
            side={orderSide}
            onSideChange={setOrderSide}
          />
        </div>

        <div className="panel">
          <PositionsTable positions={positions} livePrices={livePrices} />
        </div>
      </div>
    </div>
  );
}
