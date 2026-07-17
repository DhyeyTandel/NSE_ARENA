// screens/Leaderboard.jsx
import { useState, useEffect } from 'react';
import { LeaderboardRow } from '../components/LeaderboardRow';
import { API_URL } from '../config';

const DEMO_LEADERBOARD = [
  { rank: 1, trader: { name: 'SharpeEdge', initials: 'SE', tag: '14 trades · 12d active' }, score: 812, grade: 'Elite', returnPct: '+8.4%', drawdown: '-2.1%', value: '₹1,08,420', isYou: false, isAI: false },
  { rank: 2, trader: { name: 'ArenaBot-1', initials: 'AB', tag: '26 trades · 14d active' }, score: 764, grade: 'Pro', returnPct: '+6.2%', drawdown: '-3.8%', value: '₹1,06,200', isYou: false, isAI: true },
  { rank: 3, trader: { name: 'You', initials: 'DT', tag: '8 trades · 10d active' }, score: 724, grade: 'Pro', returnPct: '+5.1%', drawdown: '-1.5%', value: '₹1,05,100', isYou: true, isAI: false },
  { rank: 4, trader: { name: 'MomentumTrader', initials: 'MT', tag: '32 trades · 14d active' }, score: 618, grade: 'Inter', returnPct: '+4.3%', drawdown: '-7.2%', value: '₹1,04,300', isYou: false, isAI: false },
  { rank: 5, trader: { name: 'NiftyBull', initials: 'NB', tag: '5 trades · 7d active' }, score: 542, grade: 'Inter', returnPct: '+2.8%', drawdown: '-4.1%', value: '₹1,02,800', isYou: false, isAI: false },
  { rank: 6, trader: { name: 'SwingKing', initials: 'SK', tag: '18 trades · 12d active' }, score: 487, grade: 'Beginner', returnPct: '+1.2%', drawdown: '-8.5%', value: '₹1,01,200', isYou: false, isAI: false },
  { rank: 7, trader: { name: 'RetailRider', initials: 'RR', tag: '42 trades · 14d active' }, score: 421, grade: 'Beginner', returnPct: '-0.8%', drawdown: '-12.3%', value: '₹99,200', isYou: false, isAI: false },
];

export function Leaderboard() {
  const [entries, setEntries] = useState(DEMO_LEADERBOARD);
  const [season, setSeason] = useState(null);
  const [hasRealData, setHasRealData] = useState(false);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const seasonRes = await fetch(`${API_URL}/seasons/active`);
        if (seasonRes.ok) {
          const seasonData = await seasonRes.json();
          if (seasonData) setSeason(seasonData);
        }
        const lbRes = await fetch(`${API_URL}/leaderboard`);
        if (lbRes.ok) {
          const lbData = await lbRes.json();
          if (lbData.length > 0) {
            const transformed = lbData.map(entry => ({
              rank: entry.rank,
              trader: { name: entry.username, initials: entry.initials, tag: `Score ${entry.trader_score}` },
              score: entry.trader_score, grade: entry.grade,
              returnPct: `${entry.total_return_pct >= 0 ? '+' : ''}${entry.total_return_pct.toFixed(1)}%`,
              drawdown: `${entry.max_drawdown.toFixed(1)}%`,
              value: `₹${Math.round(entry.total_value).toLocaleString('en-IN')}`,
              isYou: false, isAI: entry.is_ai,
            }));
            setEntries(transformed);
            setHasRealData(true);
          }
        }
      } catch { /* Use demo data */ }
    };
    fetchData();
  }, []);

  const seasonName = season?.name || 'Season 3';
  const seasonInfo = season ? `${entries.length} traders · ${season.days_remaining} days remaining` : '47 traders · 14 days remaining';

  return (
    <div style={{ animation: 'fadeIn 0.3s var(--ease-swift)' }}>
      {/* Header */}
      <div style={{
        padding: '24px 24px 20px',
        display: 'flex', alignItems: 'center', gap: '14px',
        borderBottom: '1px solid var(--faint)',
      }}>
        <div style={{ fontSize: '20px', color: 'var(--accent)' }}>▲</div>
        <div>
          <div className="t-display" style={{
            fontSize: '20px',
            display: 'flex', alignItems: 'center', gap: '10px',
          }}>
            Season leaderboard
            <span style={{
              fontSize: '11px', fontWeight: 600, color: 'var(--accent)',
              background: 'var(--accent-soft)', border: '1px solid var(--accent-glow)',
              padding: '3px 10px', borderRadius: 'var(--r-pill)',
              fontFamily: '"JetBrains Mono", monospace',
            }}>{seasonName}</span>
            {!hasRealData && (
              <span style={{
                fontSize: '10px', fontWeight: 500, color: 'var(--muted)',
                background: 'var(--paper-lift)', border: '1px solid var(--faint)',
                padding: '2px 8px', borderRadius: 'var(--r-pill)',
              }}>Demo</span>
            )}
          </div>
          <div style={{ fontSize: '12px', color: 'var(--muted)', marginTop: '4px' }}>
            {seasonInfo}
          </div>
        </div>
      </div>

      {/* Table wrapper */}
      <div style={{
        margin: '16px 24px 24px',
        background: 'var(--card)',
        border: '1px solid var(--faint)',
        borderRadius: 'var(--r-card)',
        overflow: 'hidden',
      }}>
        {/* Column headers */}
        <div style={{
          display: 'grid', gridTemplateColumns: '40px 1fr 88px 80px 80px 80px',
          alignItems: 'center', padding: '10px 24px',
          borderBottom: '1px solid var(--faint)',
          background: 'var(--paper-lift)', gap: '8px',
        }}>
          {['#', 'Trader', 'Score', 'Return', 'Drawdown', 'Value'].map(h => (
            <div key={h} className="t-label">{h}</div>
          ))}
        </div>

        {/* Rows */}
        {entries.map(entry => (
          <LeaderboardRow key={entry.rank} {...entry} />
        ))}
      </div>
    </div>
  );
}
