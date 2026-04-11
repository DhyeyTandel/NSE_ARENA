// screens/Leaderboard.jsx
import { useState, useEffect } from 'react';
import { LeaderboardRow } from '../components/LeaderboardRow';

// Demo data (fallback)
const DEMO_LEADERBOARD = [
  {
    rank: 1, trader: { name: 'SharpeEdge', initials: 'SE', tag: '14 trades · 12d active' },
    score: 812, grade: 'Elite', returnPct: '+8.4%', drawdown: '-2.1%',
    value: '₹1,08,420', isYou: false, isAI: false,
  },
  {
    rank: 2, trader: { name: 'ArenaBot-1', initials: 'AB', tag: '26 trades · 14d active' },
    score: 764, grade: 'Pro', returnPct: '+6.2%', drawdown: '-3.8%',
    value: '₹1,06,200', isYou: false, isAI: true,
  },
  {
    rank: 3, trader: { name: 'You', initials: 'DT', tag: '8 trades · 10d active' },
    score: 724, grade: 'Pro', returnPct: '+5.1%', drawdown: '-1.5%',
    value: '₹1,05,100', isYou: true, isAI: false,
  },
  {
    rank: 4, trader: { name: 'MomentumTrader', initials: 'MT', tag: '32 trades · 14d active' },
    score: 618, grade: 'Inter', returnPct: '+4.3%', drawdown: '-7.2%',
    value: '₹1,04,300', isYou: false, isAI: false,
  },
  {
    rank: 5, trader: { name: 'NiftyBull', initials: 'NB', tag: '5 trades · 7d active' },
    score: 542, grade: 'Inter', returnPct: '+2.8%', drawdown: '-4.1%',
    value: '₹1,02,800', isYou: false, isAI: false,
  },
  {
    rank: 6, trader: { name: 'SwingKing', initials: 'SK', tag: '18 trades · 12d active' },
    score: 487, grade: 'Beginner', returnPct: '+1.2%', drawdown: '-8.5%',
    value: '₹1,01,200', isYou: false, isAI: false,
  },
  {
    rank: 7, trader: { name: 'RetailRider', initials: 'RR', tag: '42 trades · 14d active' },
    score: 421, grade: 'Beginner', returnPct: '-0.8%', drawdown: '-12.3%',
    value: '₹99,200', isYou: false, isAI: false,
  },
];

export function Leaderboard({ token }) {
  const [entries, setEntries] = useState(DEMO_LEADERBOARD);
  const [season, setSeason] = useState(null);
  const [hasRealData, setHasRealData] = useState(false);

  // Fetch real leaderboard and season data
  useEffect(() => {
    const fetchData = async () => {
      try {
        // Fetch season info
        const seasonRes = await fetch('http://localhost:8000/seasons/active');
        if (seasonRes.ok) {
          const seasonData = await seasonRes.json();
          if (seasonData) setSeason(seasonData);
        }

        // Fetch leaderboard
        const lbRes = await fetch('http://localhost:8000/leaderboard');
        if (lbRes.ok) {
          const lbData = await lbRes.json();
          if (lbData.length > 0) {
            const transformed = lbData.map(entry => ({
              rank: entry.rank,
              trader: {
                name: entry.username,
                initials: entry.initials,
                tag: `Score ${entry.trader_score}`,
              },
              score: entry.trader_score,
              grade: entry.grade,
              returnPct: `${entry.total_return_pct >= 0 ? '+' : ''}${entry.total_return_pct.toFixed(1)}%`,
              drawdown: `${entry.max_drawdown.toFixed(1)}%`,
              value: `₹${Math.round(entry.total_value).toLocaleString('en-IN')}`,
              isYou: false,  // We'd need to match user ID here
              isAI: entry.is_ai,
            }));
            setEntries(transformed);
            setHasRealData(true);
          }
        }
      } catch {
        // Use demo data
      }
    };
    fetchData();
  }, [token]);

  const seasonName = season?.name || 'Season 3';
  const seasonInfo = season
    ? `${entries.length} traders · ${season.days_remaining} days remaining`
    : '47 traders · 14 days remaining';

  return (
    <div>
      {/* Header */}
      <div style={{
        padding: '18px 20px',
        borderBottom: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', gap: '12px'
      }}>
        <div style={{ fontSize: '16px', fontWeight: 500, letterSpacing: '-0.3px' }}>
          Leaderboard
        </div>
        <div style={{
          fontSize: '10px', color: 'var(--gold)',
          background: 'var(--gold-dim)', border: '1px solid var(--gold-glow)',
          padding: '2px 8px', borderRadius: '3px',
          fontFamily: 'DM Mono, monospace'
        }}>
          {seasonName}
        </div>
        {!hasRealData && (
          <div style={{
            fontSize: '9px', color: 'var(--text3)',
            background: 'var(--ink3)', border: '1px solid var(--border)',
            padding: '2px 6px', borderRadius: '3px',
          }}>
            demo
          </div>
        )}
        <div style={{ fontSize: '11px', color: 'var(--text3)', marginLeft: 'auto' }}>
          {seasonInfo}
        </div>
      </div>

      {/* Column headers */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: '36px 1fr 88px 76px 76px 72px',
        alignItems: 'center',
        padding: '8px 20px',
        borderBottom: '1px solid var(--border)',
        gap: '8px',
      }}>
        {['#', 'Trader', 'Score', 'Return', 'Drawdown', 'Value'].map(h => (
          <div key={h} style={{
            fontSize: '10px', color: 'var(--text3)',
            textTransform: 'uppercase', letterSpacing: '.06em'
          }}>
            {h}
          </div>
        ))}
      </div>

      {/* Rows */}
      {entries.map(entry => (
        <LeaderboardRow key={entry.rank} {...entry} />
      ))}
    </div>
  );
}
