// screens/AIFeed.jsx
import { useState, useEffect } from 'react';
import { API_URL } from '../config';
import { useLeaderboard } from '../hooks/useLeaderboard';
import './Pages.css';

const BADGE = {
  buy: 'chip chip--buy',
  sell: 'chip chip--sell',
  blocked: 'chip chip--loss',
}; // hold / anything else stays neutral grey

const CLAMP_CHARS = 180; // reasoning longer than this starts clamped

const agentInitial = n => (n.includes('-') ? n.split('-')[1][0] : n[0]).toUpperCase();

function DecisionCard({ d }) {
  const [open, setOpen] = useState(false);
  const long = d.reasoning.length > CLAMP_CHARS;
  return (
    <li className="tl-item">
      <span className={`tl-dot tl-dot--${d.action}`} aria-hidden="true" />
      <article className="tl-card">
        <div className="tl-top">
          <span className={`${BADGE[d.action] || 'chip'} tl-badge`}>{d.action.toUpperCase()}</span>
          {d.ticker && <span className="tl-ticker">{d.ticker}</span>}
          {d.quantity ? <span className="muted num">{d.quantity} {d.quantity === 1 ? 'share' : 'shares'}</span> : null}
          <time className="tl-time" dateTime={d.iso || undefined}>{d.time}</time>
        </div>
        <div className="tl-agent">
          <span>{d.agent}</span>
          <span className="chip chip--ai">AI</span>
        </div>
        {d.reasoning && (
          <>
            <p className={`tl-reason${long && !open ? ' is-clamped' : ''}`}>{d.reasoning}</p>
            {long && (
              <button type="button" className="tl-more" aria-expanded={open} onClick={() => setOpen(o => !o)}>
                {open ? 'Show less' : 'Show more'}
              </button>
            )}
          </>
        )}
      </article>
    </li>
  );
}

export function AIFeed() {
  const [feed, setFeed] = useState(null); // null while loading
  const { leaderboard, loading: lbLoading } = useLeaderboard();

  const agents = leaderboard.filter(e => e.is_ai);
  const humans = leaderboard.filter(e => !e.is_ai);
  const bestAgentRank = agents.length ? Math.min(...agents.map(a => a.rank)) : null;
  const humansAbove = bestAgentRank != null ? humans.filter(h => h.rank < bestAgentRank).length : null;
  const top = leaderboard.slice(0, 50);
  const humanShare = top.length ? Math.round(top.filter(e => !e.is_ai).length / top.length * 100) : null;

  useEffect(() => {
    let cancelled = false;
    const fetchDecisions = async () => {
      let rows = [];
      try {
        const response = await fetch(`${API_URL}/ai/decisions?limit=20`);
        if (response.ok) {
          const decisions = await response.json();
          if (Array.isArray(decisions)) {
            rows = decisions.map(d => ({
              agent: d.agent_name || 'ai-agent',
              action: (d.action || 'hold').toLowerCase(),
              ticker: d.ticker || '',
              quantity: d.quantity || 0,
              iso: d.created_at || '',
              time: d.created_at
                ? new Date(d.created_at).toLocaleString('en-IN', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', hour12: true })
                : '',
              reasoning: d.reasoning || '',
            }));
          }
        }
      } catch { /* leave feed empty */ }
      if (!cancelled) setFeed(rows);
    };
    fetchDecisions();
    return () => { cancelled = true; };
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

          {feed === null && (
            <div className="panel" aria-busy="true" aria-label="Loading decisions">
              {[0, 1, 2].map(i => (
                <div key={i} className="tl-skel" style={{ borderTop: i ? '1px solid var(--border)' : 0 }}>
                  <span className="skel" style={{ '--w': '45%' }} />
                  <span className="skel" style={{ '--w': '90%' }} />
                  <span className="skel" style={{ '--w': '70%' }} />
                </div>
              ))}
            </div>
          )}
          {feed !== null && feed.length === 0 && (
            <div className="panel">
              <div className="empty">
                <svg className="empty-icon" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <rect x="5" y="8" width="14" height="11" rx="2" /><path d="M12 4v4M9 13h.01M15 13h.01M9 16h6" />
                </svg>
                <strong>No AI decisions yet</strong>
                Agent trades and their reasoning will show up here as they happen.
              </div>
            </div>
          )}
          {feed !== null && feed.length > 0 && (
            <ol className="timeline" aria-label="AI decisions, newest first">
              {feed.map((d, i) => <DecisionCard key={i} d={d} />)}
            </ol>
          )}
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--s3)' }}>
          <div className="panel">
            <div className="panel-head"><h2 className="panel-title">Humans vs agents</h2></div>
            <div className="vs-body">
              {lbLoading ? (
                <><span className="skel skel--block" style={{ '--w': '60%', '--h': '22px' }} /><span className="skel skel--block" style={{ marginTop: 'var(--s3)', '--h': '4px' }} /></>
              ) : humansAbove != null ? (
                <>
                  <div style={{ display: 'flex', alignItems: 'baseline', gap: 'var(--s2)' }}>
                    <span className="vs-big num">{humansAbove}</span>
                    <span className="muted">{humansAbove === 1 ? 'human above' : 'humans above'} the best agent</span>
                  </div>
                  <div className="bar" style={{ marginTop: 'var(--s3)' }}><span style={{ width: `${humanShare}%` }} /></div>
                  <div className="muted" style={{ fontSize: 'var(--fs-xs)', marginTop: 'var(--s2)' }}>
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
              {agents.map(a => (
                <div key={a.user_id} className="agent-row">
                  <span className="avatar avatar--ai" aria-hidden="true">{agentInitial(a.username)}</span>
                  <span className="agent-name">{a.username}</span>
                  <span className="muted num" style={{ fontSize: 'var(--fs-xs)' }}>#{a.rank}</span>
                  <span className={`agent-ret num ${a.total_return_pct >= 0 ? 'up' : 'dn'}`}>
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
