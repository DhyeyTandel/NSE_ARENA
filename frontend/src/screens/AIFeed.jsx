// screens/AIFeed.jsx
import { useState, useEffect } from 'react';
import { AIFeedEntry } from '../components/AIFeedEntry';
import { API_URL } from '../config';

const DEMO_AI_FEED = [
  {
    action: 'buy', ticker: 'RELIANCE', detail: '15 shares @ ₹2,847', time: '11:30 AM',
    reasoning: 'Reliance is showing strong support at the 2,840 level with increasing volume. The risk-reward ratio is favorable with a 2% stop loss giving us 6% upside potential to the 3,020 resistance.',
    confidence: 78,
    stats: [
      { label: 'Position', value: '₹42,705 (15.2%)', highlight: null },
      { label: 'Stop loss', value: '₹2,790', highlight: 'var(--error)' },
    ],
    status: '✓ Executed',
  },
  {
    action: 'hold', ticker: '—', detail: 'No action taken', time: '11:00 AM',
    reasoning: 'Market opened with a gap-down on global cues. Nifty is testing 22,400 support. Entering during high volatility with unclear direction would be reckless.',
    confidence: 45,
    stats: [
      { label: 'Portfolio', value: '₹1,05,100', highlight: null },
      { label: 'Day P&L', value: '-₹340', highlight: 'var(--error)' },
    ],
    status: null,
  },
  {
    action: 'sell', ticker: 'HDFCBANK', detail: '8 shares @ ₹1,642', time: '10:30 AM',
    reasoning: 'HDFC Bank has hit my take-profit target at ₹1,640. The position was entered at ₹1,580 and has delivered a clean 3.8% return. Taking profits here.',
    confidence: 82,
    stats: [
      { label: 'P&L', value: '+₹496 (+3.8%)', highlight: 'var(--success)' },
      { label: 'Hold time', value: '6 days', highlight: null },
    ],
    status: '✓ Executed',
  },
  {
    action: 'buy', ticker: 'INFY', detail: '12 shares @ ₹1,520', time: 'Yesterday 2:45 PM',
    reasoning: 'Infosys reported strong Q3 guidance revision. IT sector showing relative strength. Entering with conservative 6.5% position size.',
    confidence: 71,
    stats: [
      { label: 'Position', value: '₹18,240 (6.5%)', highlight: null },
      { label: 'Stop loss', value: '₹1,480', highlight: 'var(--error)' },
    ],
    status: '✓ Executed',
  },
];

export function AIFeed() {
  const [feed, setFeed] = useState(DEMO_AI_FEED);
  const [hasRealData, setHasRealData] = useState(false);

  useEffect(() => {
    const fetchDecisions = async () => {
      try {
        const response = await fetch(`${API_URL}/ai/decisions?limit=20`);
        if (response.ok) {
          const decisions = await response.json();
          if (decisions.length > 0) {
            const transformed = decisions.map(d => {
              const time = d.created_at
                ? new Date(d.created_at).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: true })
                : '—';
              return {
                action: d.action, ticker: d.ticker || '—',
                detail: d.quantity ? `${d.quantity} shares` : (d.action === 'hold' ? 'No action taken' : '—'),
                time, reasoning: d.reasoning || '—',
                confidence: Math.round((d.confidence || 0) * 100),
                stats: [
                  d.position_size_pct != null ? { label: 'Position size', value: `${(d.position_size_pct * 100).toFixed(1)}%`, highlight: null } : null,
                  d.stop_loss_price ? { label: 'Stop loss', value: `₹${d.stop_loss_price.toLocaleString('en-IN')}`, highlight: 'var(--error)' } : null,
                  d.guardrail_status === 'blocked' ? { label: 'Guardrail', value: 'Blocked', highlight: 'var(--error)' } : null,
                ].filter(Boolean),
                status: d.guardrail_status === 'blocked'
                  ? `Blocked — ${d.guardrail_reason || 'guardrail'}`
                  : (d.action !== 'hold' ? '✓ Executed' : null),
              };
            });
            setFeed(transformed);
            setHasRealData(true);
          }
        }
      } catch { /* Use demo data */ }
    };
    fetchDecisions();
  }, []);

  return (
    <div style={{ animation: 'fadeIn 0.3s var(--ease-swift)' }}>
      {/* Header */}
      <div style={{
        padding: '24px 24px 20px',
        display: 'flex', alignItems: 'center', gap: '14px',
        borderBottom: '1px solid var(--faint)',
      }}>
        {/* Bot avatar */}
        <div style={{
          width: '42px', height: '42px', borderRadius: '50%',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: '12px', fontWeight: 700,
          background: 'linear-gradient(135deg, var(--blurple-soft) 0%, var(--paper-lift) 100%)',
          border: '2px solid var(--blurple-glow)',
          color: 'var(--blurple)',
        }}>AB</div>

        <div style={{ flex: 1 }}>
          <div className="t-display" style={{
            fontSize: '20px',
            display: 'flex', alignItems: 'center', gap: '8px',
          }}>
            AI trading intelligence
            <span style={{
              fontSize: '10px', fontWeight: 600, color: 'var(--blurple)',
              background: 'var(--blurple-soft)', border: '1px solid var(--blurple-glow)',
              padding: '2px 8px', borderRadius: 'var(--r-pill)',
            }}>Gemini</span>
            {!hasRealData && (
              <span style={{
                fontSize: '10px', fontWeight: 500, color: 'var(--muted)',
                background: 'var(--paper-lift)', border: '1px solid var(--faint)',
                padding: '2px 8px', borderRadius: 'var(--r-pill)',
              }}>Demo</span>
            )}
          </div>
          <div style={{ fontSize: '12px', color: 'var(--muted)', marginTop: '3px' }}>
            {hasRealData
              ? `${feed.length} decisions logged`
              : 'Watch how our AI agent reasons through every trade decision'}
          </div>
        </div>

        {/* Stats */}
        <div style={{ display: 'flex', gap: '20px' }}>
          <div style={{ textAlign: 'right' }}>
            <div className="t-label">Return</div>
            <div style={{ fontFamily: '"JetBrains Mono", monospace', fontSize: '16px', fontWeight: 400, color: 'var(--success)' }}>+6.2%</div>
          </div>
          <div style={{ textAlign: 'right' }}>
            <div className="t-label">Score</div>
            <div style={{ fontFamily: '"JetBrains Mono", monospace', fontSize: '16px', fontWeight: 400, color: 'var(--blurple)' }}>764</div>
          </div>
        </div>
      </div>

      {/* Feed entries */}
      <div style={{ padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: '14px' }}>
        {feed.map((entry, i) => (
          <AIFeedEntry key={i} {...entry} />
        ))}
      </div>
    </div>
  );
}
