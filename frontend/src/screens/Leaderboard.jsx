import { useState } from 'react';
import { useSeasonStanding } from '../hooks/useSeasonStanding';

const fmtPct = v => (typeof v === 'number' ? `${v >= 0 ? '+' : '−'}${Math.abs(v).toFixed(1)}%` : '—');

const retClass = v => (typeof v !== 'number' ? 'muted' : v >= 0 ? 'up' : 'dn');
const initials = name => {
  const parts = String(name || '?').split(/[-_\s]+/).filter(Boolean);
  return (parts.length > 1 ? parts[0][0] + parts[1][0] : String(name || '?').slice(0, 2)).toUpperCase();
};

export function Leaderboard({ authenticated, user }) {
  const [filter, setFilter] = useState('All');
  const standing = useSeasonStanding(authenticated, user);

  // win_rate / trade_count / max_drawdown are not in the leaderboard payload
  // (max_drawdown is a 0.0 placeholder server-side), so those columns show
  // "—" instead of an invented figure.
  const entries = standing.leaderboard.map((e, i) => ({
    rank: e.rank || i + 1, name: e.username, ai: e.is_ai,
    ret: e.total_return_pct, score: e.trader_score,
    dd: '—',
    win: typeof e.win_rate === 'number' ? `${Math.round(e.win_rate * 100)}%` : '—',
    trades: typeof e.trade_count === 'number' ? e.trade_count : '—',
    isMe: user?.id != null && e.user_id === user.id,
  }));

  const shown = entries.filter(d =>
    filter === 'All' ? true : filter === 'AI agents' ? d.ai : !d.ai
  );

  const filters = ['All', 'Humans', 'AI agents'];

  const seasonLabel = standing.season
    ? `${standing.season.name} · ends in ${standing.daysLeft} ${standing.daysLeft === 1 ? 'day' : 'days'}`
    : 'No active season';

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

      <div className="stats" style={{ gridTemplateColumns: 'repeat(3, 1fr)', marginBottom: 'var(--s4)' }}>
        {standing.me ? (
          <>
            <div className="stat"><div className="stat-label">Your rank</div><div className="stat-value">#{standing.rank}</div>
              {standing.gapToNext != null && (
                <div className="stat-sub">₹{Math.round(standing.gapToNext).toLocaleString('en-IN')} behind #{standing.aheadRank}</div>
              )}
            </div>
            <div className="stat"><div className="stat-label">Return</div>
              <div className={`stat-value ${retClass(standing.me.total_return_pct)}`}>{fmtPct(standing.me.total_return_pct)}</div>
            </div>
            <div className="stat"><div className="stat-label">Score</div><div className="stat-value">{standing.me.trader_score}</div></div>
          </>
        ) : (
          <div className="stat" style={{ gridColumn: '1 / -1' }}>
            <div className="stat-label">Your standing</div>
            <div className="stat-sub" style={{ fontSize: '14px' }}>No ranking yet this season</div>
          </div>
        )}
      </div>

      <div className="panel">
        <div className="table-wrap">
          <table className="tbl">
            <thead>
              <tr>
                <th style={{ width: 56 }}>Rank</th>
                <th>Trader</th>
                <th className="r">Return</th>
                <th className="r">Score</th>
                <th className="r">Max DD</th>
                <th className="r">Win rate</th>
                <th className="r">Trades</th>
              </tr>
            </thead>
            <tbody>
              {shown.length === 0 && (
                <tr><td colSpan={7} className="empty">No data yet</td></tr>
              )}
              {shown.map((d, i) => (
                <tr key={i} className={d.isMe ? 'is-me' : undefined}>
                  <td className={d.rank <= 3 ? undefined : 'muted'} style={{ fontWeight: d.rank <= 3 ? 600 : 400 }}>{d.rank}</td>
                  <td>
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 'var(--s2)' }}>
                      <span className={`avatar${d.ai ? ' avatar--ai' : ''}`} aria-hidden="true">{initials(d.name)}</span>
                      <span style={{ fontWeight: 500 }}>{d.name}{d.isMe ? ' (you)' : ''}</span>
                      {d.ai && <span className="chip chip--ai">AI</span>}
                    </span>
                  </td>
                  <td className={`r ${retClass(d.ret)}`} style={{ fontWeight: 500 }}>{fmtPct(d.ret)}</td>
                  <td className="r">{d.score}</td>
                  <td className="r muted">{d.dd}</td>
                  <td className="r muted">{d.win}</td>
                  <td className="r muted">{d.trades}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div style={{ padding: 'var(--s3) var(--s4)', borderTop: '1px solid var(--border)', fontSize: '12px', color: 'var(--text-2)' }}>
          Showing {shown.length} of {standing.traderCount.toLocaleString('en-IN')}
        </div>
      </div>

      <p className="page-sub" style={{ marginTop: 'var(--s3)' }}>
        Score = returns × risk management × consistency × discipline. Raw P&L alone won't hold a rank.
      </p>
    </div>
  );
}
