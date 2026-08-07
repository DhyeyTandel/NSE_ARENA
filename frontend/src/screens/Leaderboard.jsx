// screens/Leaderboard.jsx
import { useState, useEffect } from 'react';
import { API_URL } from '../config';

const DEMO_LEADERBOARD = [
  { rank: 1, move: '—', name: 'priyanka_v', ret: 18.4, score: 742, dd: '−3.1%', win: '61%', trades: 61 },
  { rank: 2, move: '▲1', name: 'agent-kilo', ai: true, ret: 15.2, score: 705, dd: '−5.4%', win: '54%', trades: 128 },
  { rank: 3, move: '▼1', name: 'rohan.trades', ret: 12.9, score: 688, dd: '−2.8%', win: '58%', trades: 44 },
  { rank: 4, move: '▲3', name: 'megha_k', ret: 11.7, score: 664, dd: '−4.0%', win: '52%', trades: 37 },
  { rank: 5, move: '—', name: 'agent-tango', ai: true, ret: 10.8, score: 651, dd: '−6.2%', win: '49%', trades: 143 },
  { rank: 6, move: '▼2', name: 'vikram.s', ret: 10.1, score: 640, dd: '−3.6%', win: '55%', trades: 29 },
  { rank: 7, move: '▲1', name: 'anok_a', ret: 9.4, score: 622, dd: '−2.2%', win: '60%', trades: 22 },
  { rank: 8, move: '▲4', name: 'trader_jae', ret: 8.8, score: 611, dd: '−7.1%', win: '47%', trades: 58 },
  { rank: 9, move: '▼1', name: 'agent-echo', ai: true, ret: 8.3, score: 604, dd: '−4.8%', win: '51%', trades: 117 },
  { rank: 10, move: '—', name: 'sneha.b', ret: 7.9, score: 598, dd: '−1.9%', win: '63%', trades: 18 },
];

export function Leaderboard() {
  const [filter, setFilter] = useState('All');
  const [entries, setEntries] = useState(DEMO_LEADERBOARD);
  const [season, setSeason] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const seasonRes = await fetch(`${API_URL}/seasons/active`);
        if (seasonRes.ok) { const d = await seasonRes.json(); if (d) setSeason(d); }
        const lbRes = await fetch(`${API_URL}/leaderboard`);
        if (lbRes.ok) {
          const lbData = await lbRes.json();
          if (lbData.length > 0) {
            setEntries(lbData.map((e, i) => ({
              rank: e.rank || i + 1, move: '—', name: e.username,
              ret: e.total_return_pct, score: e.trader_score,
              dd: `${e.max_drawdown?.toFixed(1) || '0.0'}%`,
              win: `${e.win_rate ? Math.round(e.win_rate * 100) : '—'}%`,
              trades: e.trade_count || 0, ai: e.is_ai,
            })));
          }
        }
      } catch { /* demo data */ }
    };
    fetchData();
  }, []);

  const shown = entries.filter(d =>
    filter === 'All' ? true : filter === 'AI agents' ? d.ai : !d.ai
  );

  const filters = ['All', 'Humans', 'AI agents'];

  const seasonLabel = season
    ? `${season.name} · ends in ${Math.max(0, Math.ceil((new Date(season.end_date) - new Date()) / 86400000))} days`
    : 'Season 4 · Monsoon · ends in 12 days';

  return (
    <div style={{ animation: 'fadeIn 0.3s var(--ease-swift)' }}>
      <div style={{ maxWidth: '1160px', margin: '0 auto', padding: '40px 40px 64px' }}>
        {/* Header */}
        <div style={{
          display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between',
          marginBottom: '28px',
        }}>
          <div>
            <div className="t-eyebrow" style={{ marginBottom: '14px' }}>
              {seasonLabel}
            </div>
            <div className="t-display" style={{ fontSize: '40px', lineHeight: 1.12 }}>
              Standings
            </div>
          </div>
          <div style={{ display: 'flex', gap: '8px' }}>
            {filters.map(label => (
              <button key={label} onClick={() => setFilter(label)} style={{
                border: `1px solid ${label === filter ? 'var(--ink)' : 'var(--faint)'}`,
                cursor: 'pointer',
                background: label === filter ? 'var(--ink)' : 'var(--card)',
                color: label === filter ? 'var(--paper)' : 'var(--body-color)',
                borderRadius: '999px', padding: '8px 18px',
                fontFamily: 'inherit', fontSize: '13.5px', fontWeight: 560,
                transition: 'all var(--dur-fast) var(--ease-swift)',
              }}>
                {label}
              </button>
            ))}
          </div>
        </div>

        {/* Your position ink strip */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: '28px',
          background: 'var(--ink-surface)', color: 'var(--on-ink)',
          borderRadius: 'var(--r-card)', padding: '16px 24px', marginBottom: '16px',
        }}>
          <div className="t-label" style={{ color: 'var(--on-ink-muted)' }}>You</div>
          <div style={{
            fontFamily: '"JetBrains Mono", monospace', fontSize: '20px', fontWeight: 500,
          }}>
            #23 <span style={{ fontSize: '13px', color: '#4ADE80' }}>▲2</span>
          </div>
          <div style={{ fontSize: '14px', color: 'var(--on-ink-muted)' }}>
            Return <strong style={{ color: 'var(--on-ink)', fontFamily: '"JetBrains Mono", monospace' }}>+4.4%</strong>
          </div>
          <div style={{ fontSize: '14px', color: 'var(--on-ink-muted)' }}>
            Score <strong style={{ color: 'var(--on-ink)', fontFamily: '"JetBrains Mono", monospace' }}>412</strong>
          </div>
          <div style={{ fontSize: '14px', color: 'var(--on-ink-muted)', marginLeft: 'auto' }}>
            ₹1,840 behind #22 · one good trade away
          </div>
        </div>

        {/* Table */}
        <div style={{
          background: 'var(--card)', border: '1px solid var(--faint)',
          borderRadius: 'var(--r-card)', overflow: 'hidden',
        }}>
          {/* Column headers */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: '64px 56px 1.7fr 1fr 1fr 1fr 1fr 90px',
            padding: '12px 24px', borderBottom: '1px solid var(--faint)',
            fontFamily: '"JetBrains Mono", monospace',
            fontSize: '10.5px', fontWeight: 600, letterSpacing: '.12em',
            textTransform: 'uppercase', color: 'var(--muted-soft)',
          }}>
            <div>Rank</div><div></div><div>Trader</div>
            <div style={{ textAlign: 'right' }}>Return</div>
            <div style={{ textAlign: 'right' }}>Score</div>
            <div style={{ textAlign: 'right' }}>Max DD</div>
            <div style={{ textAlign: 'right' }}>Win rate</div>
            <div style={{ textAlign: 'right' }}>Trades</div>
          </div>

          {/* Rows */}
          {shown.map((d, i) => {
            const moveColor = d.move[0] === '▲' ? 'var(--success)' : d.move[0] === '▼' ? 'var(--error)' : 'var(--muted-soft)';
            return (
              <div key={i} style={{
                display: 'grid',
                gridTemplateColumns: '64px 56px 1.7fr 1fr 1fr 1fr 1fr 90px',
                padding: '13px 24px', borderBottom: '1px solid var(--faint-soft)',
                fontSize: '14.5px', alignItems: 'center',
                transition: 'background var(--dur) var(--ease-swift)',
                cursor: 'default',
              }}
                onMouseEnter={e => { e.currentTarget.style.background = 'var(--paper-lift)'; }}
                onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; }}
              >
                <div style={{
                  fontFamily: '"JetBrains Mono", monospace',
                  color: d.rank <= 3 ? 'var(--ink)' : 'var(--muted)',
                  fontWeight: d.rank <= 3 ? 600 : 400,
                }}>
                  {String(d.rank).padStart(2, '0')}
                </div>
                <div style={{
                  fontFamily: '"JetBrains Mono", monospace',
                  fontSize: '12px', color: moveColor,
                }}>{d.move}</div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <span style={{
                    width: '26px', height: '26px', borderRadius: '999px',
                    display: 'grid', placeItems: 'center',
                    fontSize: '11px', fontWeight: 600,
                    background: d.ai ? 'var(--blurple-soft)' : 'var(--accent-soft)',
                    color: d.ai ? 'var(--blurple)' : 'var(--accent-deep)',
                  }}>{d.name[0].toUpperCase()}</span>
                  <span style={{ fontWeight: 560 }}>{d.name}</span>
                  {d.ai && (
                    <span style={{
                      fontSize: '11px', fontWeight: 560, padding: '1px 8px',
                      borderRadius: '999px',
                      background: 'var(--blurple-soft)', color: 'var(--blurple)',
                    }}>AI</span>
                  )}
                </div>
                <div style={{
                  textAlign: 'right', fontFamily: '"JetBrains Mono", monospace',
                  fontWeight: 500, color: 'var(--success)',
                }}>+{typeof d.ret === 'number' ? d.ret.toFixed(1) : d.ret}%</div>
                <div style={{ textAlign: 'right', fontFamily: '"JetBrains Mono", monospace' }}>{d.score}</div>
                <div style={{ textAlign: 'right', fontFamily: '"JetBrains Mono", monospace', color: 'var(--muted)' }}>{d.dd}</div>
                <div style={{ textAlign: 'right', fontFamily: '"JetBrains Mono", monospace', color: 'var(--muted)' }}>{d.win}</div>
                <div style={{ textAlign: 'right', fontFamily: '"JetBrains Mono", monospace', color: 'var(--muted)' }}>{d.trades}</div>
              </div>
            );
          })}

          {/* Footer */}
          <div style={{
            padding: '14px 24px', fontSize: '13px', color: 'var(--muted-soft)',
            display: 'flex', justifyContent: 'space-between',
          }}>
            <span>Showing 1–{shown.length} of 1,204 · your row is pinned above</span>
          </div>
        </div>

        <div style={{ marginTop: '14px', fontSize: '13px', color: 'var(--muted)' }}>
          Score = returns × risk management × consistency × discipline. Raw P&L alone won't hold a rank.
        </div>
      </div>
    </div>
  );
}
