// screens/Dashboard.jsx
import { useState, useMemo, useEffect, useRef } from 'react';
import axios from 'axios';
import { TradingViewChart } from '../components/TradingViewChart';
import { OrderPanel } from '../components/OrderPanel';
import { PositionsTable } from '../components/PositionsTable';
import { useWebSocket } from '../hooks/useWebSocket';
import { usePortfolio } from '../hooks/usePortfolio';
import { useSeasonStanding } from '../hooks/useSeasonStanding';
import { API_URL, WS_URL } from '../config';
import './Dashboard.css';

const fmt2 = n => n.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const signedPct = v => `${v >= 0 ? '+' : '−'}${Math.abs(v).toFixed(2)}%`;
const chgClass = v => (typeof v !== 'number' ? 'muted' : v >= 0 ? 'up' : 'dn');

// One watchlist row. Remembers the previous price so a tick up/down can
// flash the row green/red (the overlay animation is a no-op under
// prefers-reduced-motion).
function WatchRow({ ticker, tick, selected, onPick }) {
  const last = tick?.price;
  const chg = tick?.change_pct;
  const hasChg = typeof chg === 'number';
  const prev = useRef(undefined);
  const [flash, setFlash] = useState(null);

  useEffect(() => {
    if (typeof last !== 'number') return;
    if (typeof prev.current === 'number' && prev.current !== last) {
      setFlash(f => ({ dir: last > prev.current ? 'up' : 'dn', id: (f?.id ?? 0) + 1 }));
    }
    prev.current = last;
  }, [last]);

  return (
    <li
      data-ticker={ticker} role="option" aria-selected={selected} tabIndex={0}
      className={`wl-row${selected ? ' is-selected' : ''}`}
      onClick={() => onPick(ticker)}
      onKeyDown={e => { if (e.target === e.currentTarget && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); onPick(ticker); } }}
    >
      {flash && <span key={flash.id} className={`wl-flash wl-flash--${flash.dir}`} aria-hidden="true" />}
      <span className="wl-sym">{ticker}</span>
      <span className={`wl-chg ${hasChg ? chgClass(chg) : 'muted'}`}>{hasChg ? signedPct(chg) : '—'}</span>
      <span className="wl-px">{typeof last === 'number' ? fmt2(last) : '—'}</span>
      <span className="wl-actions">
        <button type="button" className="wl-b" aria-label={`Buy ${ticker}`} title="Buy"
          onClick={e => { e.stopPropagation(); onPick(ticker, 'buy'); }}>B</button>
        <button type="button" className="wl-s" aria-label={`Sell ${ticker}`} title="Sell"
          onClick={e => { e.stopPropagation(); onPick(ticker, 'sell'); }}>S</button>
      </span>
    </li>
  );
}

export function Dashboard({ authenticated, user }) {
  const [selectedTicker, setSelectedTicker] = useState('RELIANCE');
  const [chartRange, setChartRange] = useState('1M');
  const [watchlist, setWatchlist] = useState(null); // null until /tickers answers
  const [wlSettled, setWlSettled] = useState(false); // /tickers answered or failed
  const [filter, setFilter] = useState('');
  const [orderSide, setOrderSide] = useState('buy');
  const [wlOpen, setWlOpen] = useState(false); // collapsible on narrow screens only
  const { portfolio, loading: portfolioLoading, refetch: refetchPortfolio } = usePortfolio(authenticated);
  const { prices: livePrices, connected: wsConnected } = useWebSocket(WS_URL, authenticated);

  useEffect(() => {
    let cancelled = false;
    axios.get(`${API_URL}/tickers`)
      .then(res => { if (!cancelled && Array.isArray(res.data?.tickers)) setWatchlist(res.data.tickers); })
      .catch(() => {})
      .finally(() => { if (!cancelled) setWlSettled(true); });
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

  // Only real holdings are ever shown; signed-out visitors see none.
  const positions = useMemo(
    () => (authenticated ? (portfolio?.holdings ?? []) : []),
    [portfolio, authenticated],
  );

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

  // Resolves to { ok, error } so the order panel can show the failure inline.
  const handleSubmit = async (order) => {
    if (!authenticated) return { ok: false, error: 'Sign in to trade' };
    try {
      const response = await fetch(`${API_URL}/trades`, {
        method: 'POST', credentials: 'include',
        headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
        body: JSON.stringify(order),
      });
      if (response.ok) { refetchPortfolio(); return { ok: true }; }
      let detail = '';
      try { detail = (await response.json()).detail; } catch { /* non-JSON error body */ }
      return { ok: false, error: typeof detail === 'string' && detail ? detail : 'Trade failed' };
    } catch {
      return { ok: false, error: 'Network error: trade not submitted.' };
    }
  };

  const inr = n => '₹' + Math.round(n).toLocaleString('en-IN');
  const px = n => (typeof n === 'number' ? '₹' + fmt2(n) : '—');
  const pnlUp = stats.pnl >= 0;
  const signed = signedPct;
  const statsLoading = authenticated && portfolioLoading && !portfolio;
  const wlLoading = !wlSettled && watchTickers.length === 0;

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

  const chartHeader = (
    <div className="sv-id">
      <div className="sv-sym">
        <h2>{selectedTicker}</h2>
        <span className="chip">NSE</span>
      </div>
      <div className="sv-quote">
        <span className="sv-price num">{displayPrice != null ? px(displayPrice) : '—'}</span>
        <span className={`sv-chg num ${chgClass(displayChangePct)}`}>
          {displayChangePct == null ? '—' : signed(displayChangePct)}
        </span>
        {absChange != null && (
          <span className={`sv-chg num ${chgClass(absChange)}`}>
            {absChange >= 0 ? '+' : '−'}₹{fmt2(Math.abs(absChange))}
          </span>
        )}
      </div>
    </div>
  );

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
        <ul className="wl-list" data-testid="watchlist" role="listbox" aria-label="Stocks" aria-busy={wlLoading}>
          {wlLoading && [0, 1, 2, 3, 4, 5, 6, 7].map(i => (
            <li key={i} className="wl-row wl-row--skel" aria-hidden="true">
              <span className="skel" style={{ '--w': '84px' }} />
              <span className="skel" style={{ '--w': '52px', marginLeft: 'auto' }} />
              <span className="skel" style={{ '--w': '64px' }} />
            </li>
          ))}
          {!wlLoading && watchTickers.length === 0 && (
            <li className="wl-empty">{filter.trim() ? `No stocks match "${filter.trim()}"` : 'No stocks available'}</li>
          )}
          {watchTickers.map(ticker => (
            <WatchRow
              key={ticker} ticker={ticker} tick={livePrices[ticker]}
              selected={ticker === selectedTicker} onPick={pickTicker}
            />
          ))}
        </ul>
        <div className="wl-foot">{watchTickers.length} {watchTickers.length === 1 ? 'stock' : 'stocks'}</div>
      </aside>

      {/* Content */}
      <div className="dash-main">
        <div className="dash-bar">
          <h1 className="dash-title">Overview</h1>
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

        <div className="stats">
          <div className="stat">
            <div className="stat-label">Portfolio value</div>
            <div className="stat-value num">{statsLoading ? <span className="skel" style={{ '--w': '96px', '--h': '18px' }} /> : inr(stats.totalValue)}</div>
            <div className="stat-sub num">{statsLoading ? <span className="skel" style={{ '--w': '70px' }} /> : `${inr(stats.cashBalance)} in cash`}</div>
          </div>
          <div className="stat">
            <div className="stat-label">Season P&L</div>
            <div className={`stat-value num ${statsLoading ? '' : pnlUp ? 'up' : 'dn'}`}>
              {statsLoading ? <span className="skel" style={{ '--w': '80px', '--h': '18px' }} /> : <>{pnlUp ? '+' : '−'}{inr(Math.abs(stats.pnl))}</>}
            </div>
            <div className={`stat-sub num ${statsLoading ? '' : pnlUp ? 'up' : 'dn'}`}>
              {statsLoading ? <span className="skel" style={{ '--w': '90px' }} /> : `${pnlUp ? '+' : ''}${stats.pnlPct.toFixed(1)}% on ₹1L capital`}
            </div>
          </div>
          <div className="stat">
            <div className="stat-label">Trader score</div>
            <div className="stat-value num">
              {standing.loading && authenticated ? <span className="skel" style={{ '--w': '48px', '--h': '18px' }} /> : (
                <>
                  {standing.score ? standing.score.final_score : '—'}
                  {standing.score?.grade && <> <span className="chip chip--ai stat-chip">{standing.score.grade}</span></>}
                </>
              )}
            </div>
          </div>
          <div className="stat">
            <div className="stat-label">Rank</div>
            <div className="stat-value num">
              {standing.loading && authenticated ? <span className="skel" style={{ '--w': '40px', '--h': '18px' }} /> : (standing.rank != null ? `#${standing.rank}` : '—')}
            </div>
            {standing.gapToNext != null && (
              <div className="stat-sub num">{inr(standing.gapToNext)} behind #{standing.aheadRank}</div>
            )}
          </div>
        </div>

        <div className="sv-grid">
          <div className="panel">
            <div className="sv-chart">
              <TradingViewChart key={selectedTicker} symbol={selectedTicker} height={360}
                range={chartRange} onRangeChange={setChartRange} header={chartHeader} />
            </div>
            <dl className="keystats keystats-wrap">
              {keyStats.map(([label, value, fmt]) => (
                <div key={label}>
                  <dt>{label}</dt>
                  <dd className="num">{typeof value === 'number' ? fmt(value) : '—'}</dd>
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
          <PositionsTable positions={positions} livePrices={livePrices} loading={authenticated && portfolioLoading && !portfolio} />
        </div>
      </div>
    </div>
  );
}
