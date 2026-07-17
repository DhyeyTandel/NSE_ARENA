// screens/Profile.jsx
import { useState, useEffect } from 'react';
import { KpiCard } from '../components/KpiCard';
import { TraderScoreCard } from '../components/TraderScoreCard';
import { SeasonHistory } from '../components/SeasonHistory';
import { API_URL } from '../config';

const DEMO_BREAKDOWN = [
  { key: 'returns', label: 'Returns', weight: 30, score: 0 },
  { key: 'risk', label: 'Risk management', weight: 30, score: 0 },
  { key: 'consistency', label: 'Consistency', weight: 25, score: 0 },
  { key: 'discipline', label: 'Discipline', weight: 15, score: 0 },
];

const DEMO_SEASONS = [];

export function Profile({ authenticated, user }) {
  const [scoreData, setScoreData] = useState(null);
  const [portfolioData, setPortfolioData] = useState(null);
  const [animatedScores, setAnimatedScores] = useState(
    DEMO_BREAKDOWN.map(b => ({ ...b, score: 0 }))
  );

  const displayUser = user || { username: 'DhyeyTrader', initials: 'DT' };

  useEffect(() => {
    if (!authenticated || !user) return;
    const fetchScore = async () => {
      try {
        const response = await fetch(`${API_URL}/score/${user.id}`);
        if (response.ok) setScoreData(await response.json());
      } catch { /* Use defaults */ }
    };
    const fetchPortfolio = async () => {
      try {
        const response = await fetch(`${API_URL}/portfolio`, {
          credentials: 'include',
        });
        if (response.ok) setPortfolioData(await response.json());
      } catch { /* Use defaults */ }
    };
    fetchScore();
    fetchPortfolio();
  }, [authenticated, user]);

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

  useEffect(() => {
    const timer = setTimeout(() => setAnimatedScores(breakdown), 100);
    return () => clearTimeout(timer);
  }, [scoreData]);

  // Score ring SVG
  const maxScore = 1000;
  const scorePercent = Math.min(finalScore / maxScore, 1);
  const circumference = 2 * Math.PI * 52;
  const strokeDashoffset = circumference * (1 - scorePercent);

  return (
    <div style={{ animation: 'fadeIn 0.3s var(--ease-swift)' }}>
      {/* Profile header */}
      <div style={{
        padding: '32px 24px',
        borderBottom: '1px solid var(--faint)',
        display: 'flex', alignItems: 'center', gap: '24px',
        animation: 'fadeInUp 0.4s var(--ease-swift)',
      }}>
        {/* Avatar */}
        <div style={{
          width: '64px', height: '64px', borderRadius: '50%',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: '22px', fontWeight: 700, flexShrink: 0,
          background: 'linear-gradient(135deg, var(--accent-soft) 0%, var(--paper-lift) 100%)',
          border: '3px solid var(--accent-glow)',
          color: 'var(--accent)',
          boxShadow: 'var(--shadow-accent)',
        }}>
          {displayUser.initials}
        </div>

        <div>
          <div className="t-display" style={{ fontSize: '24px' }}>
            {displayUser.username}
          </div>
          <div style={{ fontSize: '13px', color: 'var(--muted)', marginTop: '3px' }}>
            {displayUser.email || 'Paper trader · NSE Arena'}
          </div>
        </div>

        {/* Score ring */}
        <div style={{ marginLeft: 'auto', textAlign: 'center', position: 'relative' }}>
          <svg width="110" height="110" style={{ transform: 'rotate(-90deg)' }}>
            <circle cx="55" cy="55" r="52" fill="none" stroke="var(--faint)" strokeWidth="5" />
            <circle
              cx="55" cy="55" r="52" fill="none"
              stroke="var(--accent)" strokeWidth="5"
              strokeLinecap="round"
              strokeDasharray={circumference}
              strokeDashoffset={strokeDashoffset}
              style={{ transition: `stroke-dashoffset 1.2s var(--ease-swift)` }}
            />
          </svg>
          <div style={{
            position: 'absolute', top: '50%', left: '50%',
            transform: 'translate(-50%, -50%)',
          }}>
            <div style={{
              fontFamily: '"JetBrains Mono", monospace', fontSize: '28px',
              fontWeight: 400, color: 'var(--accent)', lineHeight: 1,
            }}>
              {finalScore}
            </div>
            <div style={{
              fontSize: '10px', fontWeight: 600, color: 'var(--accent)',
              marginTop: '2px', fontFamily: '"JetBrains Mono", monospace',
              letterSpacing: '.06em', textTransform: 'uppercase',
            }}>
              {grade}
            </div>
          </div>
        </div>
      </div>

      {/* Stats bar */}
      <div style={{
        display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)',
        margin: '16px 24px 0',
        background: 'var(--card)',
        border: '1px solid var(--faint)',
        borderRadius: 'var(--r-card)',
        overflow: 'hidden',
      }}>
        <KpiCard
          label="Total return"
          value={`${totalReturnPct >= 0 ? '+' : ''}${totalReturnPct.toFixed(1)}%`}
          sub={`₹${Math.round(totalValue).toLocaleString('en-IN')}`}
          variant={totalReturn >= 0 ? 'up' : 'down'} delay={0}
        />
        <KpiCard label="Cash balance"
          value={`₹${Math.round(portfolioData?.cash_balance || 100000).toLocaleString('en-IN')}`}
          sub="available" variant="default" delay={0.05}
        />
        <KpiCard label="Max drawdown" value="—" sub="—" variant="default" delay={0.1} />
        <KpiCard label="Win rate" value="—" sub="—" variant="default" delay={0.15} />
      </div>

      {/* Score breakdown */}
      <div style={{
        margin: '16px 24px 0',
        background: 'var(--card)',
        border: '1px solid var(--faint)',
        borderRadius: 'var(--r-card)',
        overflow: 'hidden',
      }}>
        <TraderScoreCard score={finalScore} grade={grade} breakdown={animatedScores} />
      </div>

      {/* Season history */}
      <div style={{
        margin: '16px 24px 24px',
        background: 'var(--card)',
        border: '1px solid var(--faint)',
        borderRadius: 'var(--r-card)',
        overflow: 'hidden',
      }}>
        <SeasonHistory seasons={DEMO_SEASONS} />
      </div>
    </div>
  );
}
