// screens/Profile.jsx
import { usePortfolio } from '../hooks/usePortfolio';
import { useSeasonStanding } from '../hooks/useSeasonStanding';

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

  const statCards = [
    { label: seasonName ? `${seasonName} return` : 'Season return', value: fmtPct(seasonReturn), color: retColor(seasonReturn), sub: 'on starting capital' },
    { label: 'Max drawdown', value: '—', color: 'var(--text)', sub: 'Not tracked yet' },
    { label: 'Win rate', value: '—', color: 'var(--text)', sub: 'Not tracked yet' },
    { label: 'Avg hold time', value: '—', color: 'var(--text)', sub: 'Not tracked yet' },
  ];

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
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--s4)' }}>
          <span className="avatar avatar--lg" aria-hidden="true">{displayUser.initials?.[0] || 'D'}</span>
          <div>
            <h1 className="page-title">{displayUser.username}</h1>
            <p className="page-sub">{displayUser.email || ''}</p>
          </div>
        </div>
        <button type="button" className="btn btn--ghost">Edit profile</button>
      </div>

      <div className="stats" style={{ marginBottom: 'var(--s4)' }}>
        {statCards.map(c => (
          <div key={c.label} className="stat">
            <div className="stat-label">{c.label}</div>
            <div className="stat-value" style={{ color: c.color }}>{c.value}</div>
            <div className="stat-sub">{c.sub}</div>
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
                  <th className="r">Trades</th>
                </tr>
              </thead>
              <tbody>
                {history.length === 0 && (
                  <tr><td colSpan={5} className="empty">No season history yet</td></tr>
                )}
                {history.map((h, i) => (
                  <tr key={i}>
                    <td><span style={{ fontWeight: 500 }}>{h.name}</span> <span className="chip chip--ai">{h.tag}</span></td>
                    <td className="r" style={{ fontWeight: 500 }}>{h.finish}</td>
                    <td className="r" style={{ color: h.retColor }}>{h.ret}</td>
                    <td className="r">{h.score}</td>
                    <td className="r muted">—</td>
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
              <span style={{ fontSize: '28px', fontWeight: 600 }}>{finalScore ?? '—'}</span>
              {grade && <span className="chip chip--ai">{grade}</span>}
            </div>
            <div className="muted" style={{ fontSize: '13px', margin: 'var(--s1) 0 var(--s4)' }}>
              {finalScore == null ? 'No score yet'
                : 500 - finalScore > 0
                ? <>{500 - finalScore} points to <strong style={{ color: 'var(--text)' }}>Disciplined</strong> (500)</>
                : 'Top tier reached'}
            </div>
            {factors.map(f => (
              <div key={f.name} style={{ marginBottom: 'var(--s3)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '13px', marginBottom: 'var(--s1)' }}>
                  <span className="muted">{f.name}</span>
                  <span style={{ fontWeight: 500 }}>{f.val}</span>
                </div>
                <div className="bar"><span style={{ width: `${f.pct}%` }} /></div>
              </div>
            ))}
            {weakest && (
              <div className="muted" style={{ fontSize: '13px', borderTop: '1px solid var(--border)', paddingTop: 'var(--s3)' }}>
                Weakest factor: {weakest.name.toLowerCase()}.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
