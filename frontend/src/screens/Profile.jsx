// screens/Profile.jsx
import { usePortfolio } from '../hooks/usePortfolio';
import { useSeasonStanding } from '../hooks/useSeasonStanding';
import './Pages.css';

const FACTOR_DEFS = [
  { name: 'Returns', key: 'returns_score', color: 'var(--accent)' },
  { name: 'Risk management', key: 'risk_score', color: 'var(--accent)' },
  { name: 'Consistency', key: 'consistency_score', color: 'var(--accent)' },
  { name: 'Discipline', key: 'discipline_score', color: 'var(--accent)' },
];

const fmtPct = v => (typeof v === 'number' ? `${v >= 0 ? '+' : '−'}${Math.abs(v).toFixed(1)}%` : '—');
const retColor = v => (typeof v !== 'number' ? 'var(--text-2)' : v >= 0 ? 'var(--gain-text)' : 'var(--loss-text)');

export function Profile({ authenticated, user }) {
  const { portfolio } = usePortfolio(authenticated);
  const standing = useSeasonStanding(authenticated, user);
  const displayUser = user || { username: 'Trader', initials: 'TR' };
  const scoreData = standing.score;

  const finalScore = scoreData ? scoreData.final_score : null;
  const grade = scoreData?.grade || null;
  const factors = FACTOR_DEFS.map(f => {
    const v = scoreData?.breakdown?.[f.key];
    return { name: f.name, val: typeof v === 'number' ? v : '—', pct: typeof v === 'number' ? v : 0, color: f.color };
  });
  const scored = factors.filter(f => typeof f.val === 'number');
  const weakest = scored.length ? scored.reduce((m, f) => (f.val < m.val ? f : m)) : null;

  const seasonReturn = portfolio?.total_return_pct ?? standing.me?.total_return_pct;
  const seasonName = standing.season?.name;

  // Only figures the API actually returns. Max drawdown, win rate and average
  // hold time are not tracked server-side, so they have no card.
  const money = n => (typeof n === 'number' ? '₹' + Math.round(n).toLocaleString('en-IN') : '—');
  const statCards = [
    { label: seasonName ? `${seasonName} return` : 'Season return', value: fmtPct(seasonReturn), color: retColor(seasonReturn), sub: 'on starting capital' },
    { label: 'Portfolio value', value: money(portfolio?.total_value), color: 'var(--text)', sub: typeof portfolio?.cash_balance === 'number' ? `${money(portfolio.cash_balance)} in cash` : null },
    { label: 'Season rank', value: standing.rank != null ? `#${standing.rank}` : '—', color: 'var(--text)', sub: standing.traderCount > 0 ? `of ${standing.traderCount.toLocaleString('en-IN')} traders` : null },
    { label: 'Trader score', value: finalScore ?? '—', color: 'var(--text)', sub: grade },
  ];
  const statsLoading = standing.loading;

  // Only the current season is available per user; the backend has no
  // per-user past-season history endpoint.
  const history = standing.season ? [{
    name: standing.season.name, tag: 'live',
    finish: standing.rank != null ? `#${standing.rank}` : '—',
    ret: fmtPct(seasonReturn), retColor: retColor(seasonReturn),
    score: finalScore ?? '—',
  }] : [];

  return (
    <div className="page">
      <div className="page-head" style={{ alignItems: 'center' }}>
        <div className="profile-id">
          <span className="avatar avatar--lg" aria-hidden="true">{displayUser.initials || displayUser.username?.slice(0, 2).toUpperCase() || '?'}</span>
          <div style={{ minWidth: 0 }}>
            <h1 className="page-title">{displayUser.username}</h1>
            {displayUser.email && <p className="page-sub">{displayUser.email}</p>}
          </div>
        </div>
      </div>

      <div className="stats" style={{ marginBottom: 'var(--s4)' }}>
        {statCards.map(c => (
          <div key={c.label} className="stat">
            <div className="stat-label">{c.label}</div>
            <div className="stat-value num" style={{ color: c.color }}>
              {statsLoading ? <span className="skel" style={{ '--w': '72px', '--h': '18px' }} /> : c.value}
            </div>
            {!statsLoading && c.sub && <div className="stat-sub num">{c.sub}</div>}
          </div>
        ))}
      </div>

      <div className="split" style={{ marginBottom: 'var(--s4)' }}>
        <div className="panel">
          <div className="panel-head"><h2 className="panel-title">Season history</h2></div>
          <div className="table-wrap">
            <table className="tbl">
              <thead>
                <tr>
                  <th>Season</th>
                  <th className="r">Finish</th>
                  <th className="r">Return</th>
                  <th className="r">Score</th>
                </tr>
              </thead>
              <tbody>
                {history.length === 0 && (
                  <tr><td colSpan={4} className="empty"><strong>No season history yet</strong>Your results appear here once a season is running.</td></tr>
                )}
                {history.map((h, i) => (
                  <tr key={i}>
                    <td><span style={{ fontWeight: 500 }}>{h.name}</span> <span className="chip chip--ai">{h.tag}</span></td>
                    <td className="r num" style={{ fontWeight: 500 }}>{h.finish}</td>
                    <td className="r num" style={{ color: h.retColor }}>{h.ret}</td>
                    <td className="r num">{h.score}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="panel">
          <div className="panel-head"><h2 className="panel-title">Trader score</h2></div>
          <div style={{ padding: 'var(--s4)' }}>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 'var(--s2)' }}>
              <span className="score-big num">{finalScore ?? '—'}</span>
              {grade && <span className="chip chip--ai">{grade}</span>}
            </div>
            <div className="muted" style={{ fontSize: 'var(--fs-sm)', margin: 'var(--s1) 0 var(--s4)' }}>
              {finalScore == null ? 'No score yet'
                : 500 - finalScore > 0
                ? <>{500 - finalScore} points to <strong style={{ color: 'var(--text)' }}>Disciplined</strong> (500)</>
                : 'Top tier reached'}
            </div>
            {factors.map(f => (
              <div key={f.name} className="factor">
                <div className="factor-row">
                  <span className="muted">{f.name}</span>
                  <span className="num" style={{ fontWeight: 500 }}>{f.val}</span>
                </div>
                <div className="bar"><span style={{ width: `${f.pct}%` }} /></div>
              </div>
            ))}
            {weakest && (
              <div className="muted" style={{ fontSize: 'var(--fs-sm)', borderTop: '1px solid var(--border)', paddingTop: 'var(--s3)' }}>
                Weakest factor: {weakest.name.toLowerCase()}.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
