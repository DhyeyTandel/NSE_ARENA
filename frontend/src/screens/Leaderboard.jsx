import { useState } from 'react';
import { useSeasonStanding } from '../hooks/useSeasonStanding';
import './Pages.css';

const fmtPct = v => (typeof v === 'number' ? `${v >= 0 ? '+' : '−'}${Math.abs(v).toFixed(1)}%` : '—');

const retClass = v => (typeof v !== 'number' ? 'muted' : v >= 0 ? 'up' : 'dn');
const initials = name => {
  const parts = String(name || '?').split(/[-_\s]+/).filter(Boolean);
  return (parts.length > 1 ? parts[0][0] + parts[1][0] : String(name || '?').slice(0, 2)).toUpperCase();
};

export function Leaderboard({ authenticated, user }) {
  const [filter, setFilter] = useState('All');
  const standing = useSeasonStanding(authenticated, user);

  // The leaderboard payload carries no win_rate / trade_count / drawdown.
  // Those columns only appear if the API starts sending them, so no cell is
  // ever filled with an invented figure.
  const entries = standing.leaderboard.map((e, i) => ({
    rank: e.rank || i + 1, name: e.username, ai: e.is_ai,
    ret: e.total_return_pct, score: e.trader_score,
    win: typeof e.win_rate === 'number' ? `${Math.round(e.win_rate * 100)}%` : null,
    trades: typeof e.trade_count === 'number' ? e.trade_count : null,
    isMe: user?.id != null && e.user_id === user.id,
  }));
  const showWin = entries.some(e => e.win != null);
  const showTrades = entries.some(e => e.trades != null);
  const colCount = 4 + (showWin ? 1 : 0) + (showTrades ? 1 : 0);

  const shown = entries.filter(d =>
    filter === 'All' ? true : filter === 'AI agents' ? d.ai : !d.ai
  );

  const filters = ['All', 'Humans', 'AI agents'];

  const seasonLabel = standing.season
    ? `${standing.season.name} · ends in ${standing.daysLeft} ${standing.daysLeft === 1 ? 'day' : 'days'}`
    : standing.loading ? 'Loading season' : 'No active season';

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1 className="page-title">Leaderboard</h1>
          <p className="page-sub">{seasonLabel}</p>
        </div>
        <div className="seg" role="group" aria-label="Filter traders">
          {filters.map(label => (
            <button key={label} type="button" className={label === filter ? 'is-active' : ''}
              aria-pressed={label === filter} onClick={() => setFilter(label)}>
              {label}
            </button>
          ))}
        </div>
      </div>

      <div className="stats lb-stats" style={{ '--cols': standing.me ? 3 : 1 }}>
        {standing.loading ? (
          [0, 1, 2].map(i => (
            <div className="stat" key={i}>
              <div className="stat-label"><span className="skel" style={{ '--w': '60px' }} /></div>
              <div className="stat-value"><span className="skel" style={{ '--w': '80px', '--h': '18px' }} /></div>
            </div>
          ))
        ) : standing.me ? (
          <>
            <div className="stat"><div className="stat-label">Your rank</div><div className="stat-value num">#{standing.rank}</div>
              {standing.gapToNext != null && (
                <div className="stat-sub num">₹{Math.round(standing.gapToNext).toLocaleString('en-IN')} behind #{standing.aheadRank}</div>
              )}
            </div>
            <div className="stat"><div className="stat-label">Return</div>
              <div className={`stat-value num ${retClass(standing.me.total_return_pct)}`}>{fmtPct(standing.me.total_return_pct)}</div>
            </div>
            <div className="stat"><div className="stat-label">Score</div><div className="stat-value num">{standing.me.trader_score}</div></div>
          </>
        ) : (
          <div className="stat">
            <div className="stat-label">Your standing</div>
            <div className="stat-sub" style={{ fontSize: 'var(--fs-md)' }}>No ranking yet this season</div>
          </div>
        )}
      </div>

      <div className="panel lb-panel">
        <div className="table-wrap table-wrap--sticky">
          <table className="tbl">
            <thead>
              <tr>
                <th style={{ width: 64 }}>Rank</th>
                <th>Trader</th>
                <th className="r">Return</th>
                <th className="r">Score</th>
                {showWin && <th className="r">Win rate</th>}
                {showTrades && <th className="r">Trades</th>}
              </tr>
            </thead>
            <tbody>
              {standing.loading && [0, 1, 2, 3, 4, 5].map(i => (
                <tr key={`s${i}`} aria-hidden="true">
                  <td><span className="skel" style={{ '--w': '24px' }} /></td>
                  <td><span className="skel" style={{ '--w': '140px' }} /></td>
                  <td className="r"><span className="skel" style={{ '--w': '48px' }} /></td>
                  <td className="r"><span className="skel" style={{ '--w': '36px' }} /></td>
                  {showWin && <td className="r"><span className="skel" style={{ '--w': '36px' }} /></td>}
                  {showTrades && <td className="r"><span className="skel" style={{ '--w': '30px' }} /></td>}
                </tr>
              ))}
              {!standing.loading && shown.length === 0 && (
                <tr><td colSpan={colCount} className="empty">
                  <strong>{entries.length === 0 ? 'No traders ranked yet' : `No ${filter === 'AI agents' ? 'AI agents' : 'humans'} ranked yet`}</strong>
                  Rankings appear once traders have placed trades this season.
                </td></tr>
              )}
              {shown.map((d, i) => (
                <tr key={i} className={d.isMe ? 'is-me' : undefined}>
                  <td>
                    <span className={`rank${d.rank <= 3 ? ` rank--${d.rank}` : ''}`}>{d.rank}</span>
                  </td>
                  <td>
                    <span className="trader">
                      <span className={`avatar${d.ai ? ' avatar--ai' : ''}`} aria-hidden="true">{initials(d.name)}</span>
                      <span className="trader-name">{d.name}{d.isMe ? ' (you)' : ''}</span>
                      {d.ai && <span className="chip chip--ai">AI</span>}
                    </span>
                  </td>
                  <td className={`r num ret ${retClass(d.ret)}`}>{fmtPct(d.ret)}</td>
                  <td className="r num">{d.score}</td>
                  {showWin && <td className="r num muted">{d.win ?? '—'}</td>}
                  {showTrades && <td className="r num muted">{d.trades ?? '—'}</td>}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="lb-foot">
          Showing {shown.length} of {standing.traderCount.toLocaleString('en-IN')}
        </div>
      </div>

      <p className="page-sub" style={{ marginTop: 'var(--s3)' }}>
        Score = returns × risk management × consistency × discipline. Raw P&L alone won't hold a rank.
      </p>
    </div>
  );
}
