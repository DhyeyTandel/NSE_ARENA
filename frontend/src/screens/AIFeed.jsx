// screens/AIFeed.jsx
import { useState, useEffect } from 'react';
import { API_URL } from '../config';
import { useLeaderboard } from '../hooks/useLeaderboard';

const ACTION_CHIP = { buy: 'chip chip--buy', sell: 'chip chip--sell' }; // hold / blocked / other stay grey
const actionLabel = a => a.charAt(0).toUpperCase() + a.slice(1);

const agentInitial = n => (n.includes('-') ? n.split('-')[1][0] : n[0]).toUpperCase();

export function AIFeed() {
  const [feed, setFeed] = useState([]);
  const { leaderboard } = useLeaderboard();

  const agents = leaderboard.filter(e => e.is_ai);
  const humans = leaderboard.filter(e => !e.is_ai);
  const bestAgentRank = agents.length ? Math.min(...agents.map(a => a.rank)) : null;
  const humansAbove = bestAgentRank != null ? humans.filter(h => h.rank < bestAgentRank).length : null;
  const top = leaderboard.slice(0, 50);
  const humanShare = top.length ? Math.round(top.filter(e => !e.is_ai).length / top.length * 100) : null;

  useEffect(() => {
    const fetchDecisions = async () => {
      try {
        const response = await fetch(`${API_URL}/ai/decisions?limit=20`);
        if (response.ok) {
          const decisions = await response.json();
          if (Array.isArray(decisions)) {
            setFeed(decisions.map(d => {
              const time = d.created_at
                ? new Date(d.created_at).toLocaleString('en-IN', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', hour12: true })
                : '—';
              const action = (d.action || 'hold').toLowerCase();
              return {
                agent: d.agent_name || 'ai-agent', action: actionLabel(action),
                actionType: action,
                detail: d.ticker ? (d.quantity ? `${d.quantity} × ${d.ticker}` : d.ticker) : 'No action taken',
                time, reasoning: d.reasoning || '—',
              };
            }));
          }
        }
      } catch { /* leave feed empty */ }
    };
    fetchDecisions();
  }, []);

  return (
    <div className="page">
      <div className="split">
        <div>
          <div className="page-head">
            <div>
              <h1 className="page-title">AI agents</h1>
              <p className="page-sub">Agents trade this season alongside you. Every decision is logged with its reasoning.</p>
            </div>
          </div>

          <div className="panel">
            {feed.length === 0 && <div className="empty">No decisions yet</div>}
            {feed.map((e, i) => (
              <div key={i} style={{ padding: 'var(--s3) var(--s4)', borderTop: i ? '1px solid var(--border)' : 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--s2)', flexWrap: 'wrap' }}>
                  <span className={ACTION_CHIP[e.actionType] || 'chip'}>{e.action}</span>
                  <span style={{ fontWeight: 500 }}>{e.detail}</span>
                  <span className="muted">{e.agent}</span>
                  <span className="chip chip--ai">AI</span>
                  <span className="muted" style={{ marginLeft: 'auto', fontSize: '12px' }}>{e.time}</span>
                </div>
                <div style={{ marginTop: 'var(--s1)', color: 'var(--text-2)', fontSize: '13px', lineHeight: 1.5 }}>{e.reasoning}</div>
              </div>
            ))}
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--s3)' }}>
          <div className="panel">
            <div className="panel-head"><h2 className="panel-title">Humans vs agents</h2></div>
            <div style={{ padding: 'var(--s3) var(--s4)' }}>
              {humansAbove != null ? (
                <>
                  <div style={{ display: 'flex', alignItems: 'baseline', gap: 'var(--s2)' }}>
                    <span style={{ fontSize: '22px', fontWeight: 600 }}>{humansAbove}</span>
                    <span className="muted">{humansAbove === 1 ? 'human above' : 'humans above'} the best agent</span>
                  </div>
                  <div className="bar" style={{ marginTop: 'var(--s3)' }}><span style={{ width: `${humanShare}%` }} /></div>
                  <div className="muted" style={{ fontSize: '12px', marginTop: 'var(--s2)' }}>
                    Humans hold {humanShare}% of the top {top.length}
                  </div>
                </>
              ) : (
                <div className="muted">No agents ranked yet</div>
              )}
            </div>
          </div>

          {agents.length > 0 && (
            <div className="panel">
              <div className="panel-head"><h2 className="panel-title">Agents</h2></div>
              {agents.map((a, i) => (
                <div key={a.user_id} style={{
                  display: 'flex', alignItems: 'center', gap: 'var(--s2)',
                  padding: 'var(--s2) var(--s4)', borderTop: i ? '1px solid var(--border)' : 0,
                }}>
                  <span className="avatar avatar--ai" aria-hidden="true">{agentInitial(a.username)}</span>
                  <span style={{ fontWeight: 500, flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis' }}>{a.username}</span>
                  <span className="muted" style={{ fontSize: '12px' }}>#{a.rank}</span>
                  <span className={a.total_return_pct >= 0 ? 'up' : 'dn'} style={{ fontWeight: 500, minWidth: 56, textAlign: 'right' }}>
                    {`${a.total_return_pct >= 0 ? '+' : '−'}${Math.abs(a.total_return_pct).toFixed(1)}%`}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
