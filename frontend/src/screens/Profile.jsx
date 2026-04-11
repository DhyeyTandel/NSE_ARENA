// screens/Profile.jsx
import { useState, useEffect } from 'react';
import { KpiCard } from '../components/KpiCard';
import { TraderScoreCard } from '../components/TraderScoreCard';
import { SeasonHistory } from '../components/SeasonHistory';

const DEMO_BREAKDOWN = [
  { key: 'returns', label: 'Returns', weight: 30, score: 0 },
  { key: 'risk', label: 'Risk management', weight: 30, score: 0 },
  { key: 'consistency', label: 'Consistency', weight: 25, score: 0 },
  { key: 'discipline', label: 'Discipline', weight: 15, score: 0 },
];

const DEMO_SEASONS = [];

export function Profile({ token, user }) {
  const [scoreData, setScoreData] = useState(null);
  const [portfolioData, setPortfolioData] = useState(null);
  const [animatedScores, setAnimatedScores] = useState(
    DEMO_BREAKDOWN.map(b => ({ ...b, score: 0 }))
  );

  const displayUser = user || { username: 'DhyeyTrader', initials: 'DT' };

  // Fetch real score data
  useEffect(() => {
    if (!token || !user) return;

    const fetchScore = async () => {
      try {
        const response = await fetch(`http://localhost:8000/score/${user.id}`);
        if (response.ok) {
          const data = await response.json();
          setScoreData(data);
        }
      } catch {
        // Use defaults
      }
    };

    const fetchPortfolio = async () => {
      try {
        const response = await fetch('http://localhost:8000/portfolio', {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (response.ok) {
          const data = await response.json();
          setPortfolioData(data);
        }
      } catch {
        // Use defaults
      }
    };

    fetchScore();
    fetchPortfolio();
  }, [token, user]);

  // Build breakdown from score data or defaults
  const breakdown = scoreData ? [
    { key: 'returns', label: 'Returns', weight: 30, score: scoreData.breakdown.returns_score },
    { key: 'risk', label: 'Risk management', weight: 30, score: scoreData.breakdown.risk_score },
    { key: 'consistency', label: 'Consistency', weight: 25, score: scoreData.breakdown.consistency_score },
    { key: 'discipline', label: 'Discipline', weight: 15, score: scoreData.breakdown.discipline_score },
  ] : DEMO_BREAKDOWN;

  const finalScore = scoreData?.final_score || 300;
  const grade = scoreData?.grade || 'Beginner';

  const totalReturn = portfolioData?.total_return || 0;
  const totalReturnPct = portfolioData?.total_return_pct || 0;
  const totalValue = portfolioData?.total_value || 100000;

  // Animate score bars on mount
  useEffect(() => {
    const timer = setTimeout(() => {
      setAnimatedScores(breakdown);
    }, 100);
    return () => clearTimeout(timer);
  }, [scoreData]);

  return (
    <div>
      {/* Profile header */}
      <div style={{
        padding: '24px 20px',
        borderBottom: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', gap: '20px'
      }}>
        {/* Avatar */}
        <div style={{
          width: '48px', height: '48px', borderRadius: '50%',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: '16px', fontWeight: 600, flexShrink: 0,
          background: 'var(--gold-dim)', border: '1px solid var(--gold-glow)',
          color: 'var(--gold)'
        }}>
          {displayUser.initials}
        </div>

        <div>
          <div style={{ fontSize: '16px', fontWeight: 500, letterSpacing: '-0.3px' }}>
            {displayUser.username}
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text3)', marginTop: '2px' }}>
            {displayUser.email || 'Paper trader'}
          </div>
        </div>

        {/* Big score */}
        <div style={{ marginLeft: 'auto', textAlign: 'right' }}>
          <div style={{
            fontFamily: 'DM Mono, monospace', fontSize: '40px',
            fontWeight: 300, color: 'var(--gold)', lineHeight: 1,
            letterSpacing: '-1px'
          }}>
            {finalScore}
          </div>
          <div style={{
            fontSize: '11px', color: 'var(--gold)',
            marginTop: '4px', fontFamily: 'DM Mono, monospace'
          }}>
            {grade}
          </div>
        </div>
      </div>

      {/* 4-stat bar */}
      <div style={{
        display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr',
        borderBottom: '1px solid var(--border)',
      }}>
        <KpiCard
          label="Total return"
          value={`${totalReturnPct >= 0 ? '+' : ''}${totalReturnPct.toFixed(1)}%`}
          sub={`₹${Math.round(totalValue).toLocaleString('en-IN')}`}
          variant={totalReturn >= 0 ? 'up' : 'down'}
        />
        <KpiCard label="Cash balance"
          value={`₹${Math.round(portfolioData?.cash_balance || 100000).toLocaleString('en-IN')}`}
          sub="available" variant="default"
        />
        <KpiCard label="Max drawdown" value="—" sub="—" variant="default" />
        <KpiCard label="Win rate" value="—" sub="—" variant="default" />
      </div>

      {/* Score breakdown */}
      <div style={{ borderBottom: '1px solid var(--border)' }}>
        <TraderScoreCard score={finalScore} grade={grade} breakdown={animatedScores} />
      </div>

      {/* Season history */}
      <SeasonHistory seasons={DEMO_SEASONS} />
    </div>
  );
}
