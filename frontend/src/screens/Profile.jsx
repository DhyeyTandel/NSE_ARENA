// screens/Profile.jsx
import { useState, useEffect } from 'react';
import { API_URL } from '../config';

const DEMO_FACTORS = [
  { name: 'Returns', val: 118, pct: 59, color: 'var(--accent)' },
  { name: 'Risk management', val: 124, pct: 62, color: 'var(--accent)' },
  { name: 'Consistency', val: 102, pct: 51, color: 'var(--accent)' },
  { name: 'Discipline', val: 68, pct: 34, color: 'var(--accent-deep)' },
];

const DEMO_HISTORY = [
  { name: 'Season 4 · Monsoon', tag: 'live', tagBg: 'var(--accent-soft)', tagFg: 'var(--accent-deep)', finish: '#23', finWeight: 600, ret: '+4.4%', retColor: 'var(--success)', score: 412, trades: 19 },
  { name: 'Season 3 · Summer', tag: 'final', tagBg: 'var(--faint-soft)', tagFg: 'var(--muted)', finish: '#11', finWeight: 400, ret: '+9.2%', retColor: 'var(--success)', score: 534, trades: 31 },
  { name: 'Season 2 · Spring', tag: 'final', tagBg: 'var(--faint-soft)', tagFg: 'var(--muted)', finish: '#204', finWeight: 400, ret: '−6.8%', retColor: 'var(--error)', score: 187, trades: 74 },
];

export function Profile({ authenticated, user }) {
  const [scoreData, setScoreData] = useState(null);
  const [portfolioData, setPortfolioData] = useState(null);
  const displayUser = user || { username: 'Trader', initials: 'TR' };

  useEffect(() => {
    if (!authenticated || !user) return;
    const fetchScore = async () => {
      try {
        const r = await fetch(`${API_URL}/score/${user.id}`);
        if (r.ok) setScoreData(await r.json());
      } catch { /* fall back to demo data below */ }
    };
    const fetchPortfolio = async () => {
      try {
        const r = await fetch(`${API_URL}/portfolio`, { credentials: 'include' });
        if (r.ok) setPortfolioData(await r.json());
      } catch { /* fall back to demo data below */ }
    };
    fetchScore(); fetchPortfolio();
  }, [authenticated, user]);

  const finalScore = scoreData?.final_score || 412;
  const grade = scoreData?.grade || 'Consistent';
  const factors = scoreData ? [
    { name: 'Returns', val: scoreData.breakdown.returns_score, pct: scoreData.breakdown.returns_score, color: 'var(--accent)' },
    { name: 'Risk management', val: scoreData.breakdown.risk_score, pct: scoreData.breakdown.risk_score, color: 'var(--accent)' },
    { name: 'Consistency', val: scoreData.breakdown.consistency_score, pct: scoreData.breakdown.consistency_score, color: 'var(--accent)' },
    { name: 'Discipline', val: scoreData.breakdown.discipline_score, pct: scoreData.breakdown.discipline_score, color: 'var(--accent-deep)' },
  ] : DEMO_FACTORS;

  const statCards = [
    { label: 'Season 4 return', value: `+${portfolioData?.total_return_pct?.toFixed(1) || '4.4'}%`, color: 'var(--success)', sub: 'vs NIFTY 50 +2.1% same period' },
    { label: 'Max drawdown', value: '−3.6%', color: 'var(--ink)', sub: 'Better than 71% of the field' },
    { label: 'Win rate', value: '58%', color: 'var(--ink)', sub: '11 of 19 trades closed green' },
    { label: 'Avg hold time', value: '3.2d', color: 'var(--ink)', sub: 'Swing trader profile' },
  ];

  return (
    <div style={{ animation: 'fadeIn 0.3s var(--ease-swift)' }}>
      <div style={{ maxWidth: '1160px', margin: '0 auto', padding: '40px 40px 64px' }}>
        {/* Identity */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '22px', marginBottom: '32px' }}>
          <div style={{
            width: '72px', height: '72px', borderRadius: '999px',
            background: 'var(--accent-soft)', color: 'var(--accent-deep)',
            display: 'grid', placeItems: 'center',
            fontFamily: '"Newsreader", Georgia, serif', fontSize: '30px',
          }}>{displayUser.initials?.[0] || 'D'}</div>
          <div>
            <div className="t-display" style={{ fontSize: '34px' }}>{displayUser.username}</div>
            <div style={{ fontSize: '14px', color: 'var(--muted)', marginTop: '2px' }}>
              {displayUser.email || 'Trading since Season 2 · 3 seasons, best finish #11'}
            </div>
          </div>
          <button style={{
            marginLeft: 'auto', border: '1px solid var(--faint)',
            cursor: 'pointer', background: 'var(--card)',
            borderRadius: '999px', padding: '9px 20px',
            fontFamily: 'inherit', fontSize: '14px', fontWeight: 560,
            color: 'var(--body-color)',
            transition: 'all var(--dur-fast) var(--ease-swift)',
          }}
            onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--ink)'; }}
            onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--faint)'; }}
          >Edit profile</button>
        </div>

        {/* Score + Stats grid */}
        <div style={{
          display: 'grid', gridTemplateColumns: '1fr 1fr 1fr',
          gap: '16px', marginBottom: '16px',
        }}>
          {/* Score breakdown (ink card) */}
          <div style={{
            background: 'var(--ink-surface)', color: 'var(--on-ink)',
            borderRadius: 'var(--r-card)', padding: '24px',
          }}>
            <div style={{
              fontFamily: '"JetBrains Mono", monospace',
              fontSize: '10.5px', fontWeight: 600, letterSpacing: '.14em',
              textTransform: 'uppercase', color: 'var(--on-ink-muted)', marginBottom: '14px',
            }}>Trader score</div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: '12px', marginBottom: '4px' }}>
              <span style={{
                fontFamily: '"JetBrains Mono", monospace',
                fontSize: '44px', fontWeight: 500, letterSpacing: '-0.01em',
              }}>{finalScore}</span>
              <span style={{
                fontSize: '12.5px', fontWeight: 560, padding: '2px 10px',
                borderRadius: '999px', background: '#3A2313', color: '#FF8A4D',
              }}>{grade}</span>
            </div>
            <div style={{ fontSize: '13px', color: 'var(--on-ink-muted)', marginBottom: '18px' }}>
              {500 - finalScore > 0
                ? <>{500 - finalScore} points to <strong style={{ color: 'var(--on-ink)' }}>Disciplined</strong> (500)</>
                : 'Top tier reached'}
            </div>
            {factors.map(f => (
              <div key={f.name} style={{ marginBottom: '12px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12.5px', marginBottom: '5px' }}>
                  <span style={{ color: '#C9C0B2' }}>{f.name}</span>
                  <span style={{ fontFamily: '"JetBrains Mono", monospace', color: 'var(--on-ink)' }}>{f.val}</span>
                </div>
                <div style={{ height: '4px', background: '#332D23', borderRadius: '999px', overflow: 'hidden' }}>
                  <div style={{
                    width: `${f.pct}%`, height: '100%',
                    background: f.color, borderRadius: '999px',
                    transition: 'width var(--dur-slow) var(--ease-swift)',
                  }} />
                </div>
              </div>
            ))}
            <div style={{
              fontSize: '12.5px', color: 'var(--on-ink-muted)',
              borderTop: '1px solid #332D23', paddingTop: '12px', marginTop: '4px',
            }}>
              Weakest factor: discipline. Two revenge trades last week cost you ~30 points.
            </div>
          </div>

          {/* Stat cards (2×2 grid spanning 2 columns) */}
          <div style={{
            gridColumn: 'span 2',
            display: 'grid', gridTemplateColumns: '1fr 1fr',
            gap: '16px', alignContent: 'start',
          }}>
            {statCards.map(c => (
              <div key={c.label} style={{
                background: 'var(--card)', border: '1px solid var(--faint)',
                borderRadius: 'var(--r-card)', padding: '20px 22px',
              }}>
                <div className="t-label" style={{ marginBottom: '8px' }}>{c.label}</div>
                <div style={{
                  fontFamily: '"JetBrains Mono", monospace',
                  fontSize: '26px', fontWeight: 500, color: c.color,
                }}>{c.value}</div>
                <div style={{ fontSize: '13px', color: 'var(--muted)', marginTop: '4px' }}>{c.sub}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Season history */}
        <div style={{
          background: 'var(--card)', border: '1px solid var(--faint)',
          borderRadius: 'var(--r-card)', overflow: 'hidden',
        }}>
          <div style={{
            display: 'flex', alignItems: 'baseline', gap: '12px',
            padding: '16px 22px', borderBottom: '1px solid var(--faint)',
          }}>
            <div className="t-title" style={{ fontSize: '19px' }}>Season history</div>
          </div>
          <div style={{
            display: 'grid', gridTemplateColumns: '1.4fr 1fr 1fr 1fr 1fr',
            padding: '10px 22px', borderBottom: '1px solid var(--faint-soft)',
            fontFamily: '"JetBrains Mono", monospace',
            fontSize: '10.5px', fontWeight: 600, letterSpacing: '.12em',
            textTransform: 'uppercase', color: 'var(--muted-soft)',
          }}>
            <div>Season</div>
            <div style={{ textAlign: 'right' }}>Finish</div>
            <div style={{ textAlign: 'right' }}>Return</div>
            <div style={{ textAlign: 'right' }}>Score</div>
            <div style={{ textAlign: 'right' }}>Trades</div>
          </div>
          {DEMO_HISTORY.map((h, i) => (
            <div key={i} style={{
              display: 'grid', gridTemplateColumns: '1.4fr 1fr 1fr 1fr 1fr',
              padding: '13px 22px', borderBottom: '1px solid var(--faint-soft)',
              fontSize: '14.5px', alignItems: 'baseline',
            }}>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: '10px' }}>
                <span style={{ fontWeight: 600 }}>{h.name}</span>
                <span style={{
                  fontSize: '11.5px', padding: '1px 8px', borderRadius: '999px',
                  background: h.tagBg, color: h.tagFg, fontWeight: 560,
                }}>{h.tag}</span>
              </div>
              <div style={{
                textAlign: 'right', fontFamily: '"JetBrains Mono", monospace',
                fontWeight: h.finWeight,
              }}>{h.finish}</div>
              <div style={{
                textAlign: 'right', fontFamily: '"JetBrains Mono", monospace',
                color: h.retColor,
              }}>{h.ret}</div>
              <div style={{
                textAlign: 'right', fontFamily: '"JetBrains Mono", monospace',
              }}>{h.score}</div>
              <div style={{
                textAlign: 'right', fontFamily: '"JetBrains Mono", monospace',
                color: 'var(--muted)',
              }}>{h.trades}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
