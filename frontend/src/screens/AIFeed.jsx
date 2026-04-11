// screens/AIFeed.jsx
import { useState, useEffect } from 'react';
import { AIFeedEntry } from '../components/AIFeedEntry';

const DEMO_AI_FEED = [
  {
    action: 'buy',
    ticker: 'RELIANCE',
    detail: '15 shares @ ₹2,847',
    time: '11:30 AM',
    reasoning: 'Reliance is showing strong support at the 2,840 level with increasing volume. The risk-reward ratio is favorable with a 2% stop loss giving us 6% upside potential to the 3,020 resistance. My Trader Score is stable so I can afford this measured exposure.',
    confidence: 78,
    stats: [
      { label: 'Position', value: '₹42,705 (15.2%)', highlight: null },
      { label: 'Stop loss', value: '₹2,790', highlight: 'var(--dn)' },
      { label: 'Recovery needed', value: '+0.0%', highlight: 'var(--gold)' },
    ],
    status: '✓ Executed',
  },
  {
    action: 'hold',
    ticker: '—',
    detail: 'No action taken',
    time: '11:00 AM',
    reasoning: 'Market opened with a gap-down on global cues. Nifty is testing 22,400 support. I chose not to trade because entering during high volatility with unclear direction would be reckless. My current portfolio is balanced and I would rather miss a recovery rally than catch a falling knife.',
    confidence: 45,
    stats: [
      { label: 'Portfolio', value: '₹1,05,100', highlight: null },
      { label: 'Day P&L', value: '-₹340', highlight: 'var(--dn)' },
      { label: 'Recovery needed', value: '+0.3%', highlight: 'var(--gold)' },
    ],
    status: null,
  },
  {
    action: 'sell',
    ticker: 'HDFCBANK',
    detail: '8 shares @ ₹1,642',
    time: '10:30 AM',
    reasoning: 'HDFC Bank has hit my take-profit target at ₹1,640. The position was entered at ₹1,580 and has delivered a clean 3.8% return. Taking profits here because banking stocks face headwinds from the upcoming RBI policy and I want to lock in gains while my Trader Score is trending upward.',
    confidence: 82,
    stats: [
      { label: 'P&L', value: '+₹496 (+3.8%)', highlight: 'var(--up)' },
      { label: 'Hold time', value: '6 days', highlight: null },
      { label: 'Recovery needed', value: '+0.0%', highlight: 'var(--gold)' },
    ],
    status: '✓ Executed',
  },
  {
    action: 'buy',
    ticker: 'INFY',
    detail: '12 shares @ ₹1,520',
    time: 'Yesterday 2:45 PM',
    reasoning: 'Infosys reported strong Q3 guidance revision. IT sector is showing relative strength against Nifty. Entering with a conservative 6.5% position size. Stop loss at ₹1,480 limits downside to 2.6% while the target at ₹1,600 offers 5.3% upside.',
    confidence: 71,
    stats: [
      { label: 'Position', value: '₹18,240 (6.5%)', highlight: null },
      { label: 'Stop loss', value: '₹1,480', highlight: 'var(--dn)' },
      { label: 'Recovery needed', value: '+0.0%', highlight: 'var(--gold)' },
    ],
    status: '✓ Executed',
  },
];

export function AIFeed() {
  const [feed, setFeed] = useState(DEMO_AI_FEED);
  const [hasRealData, setHasRealData] = useState(false);

  // Try to fetch real AI decisions from backend
  useEffect(() => {
    const fetchDecisions = async () => {
      try {
        const response = await fetch('http://localhost:8000/ai/decisions?limit=20');
        if (response.ok) {
          const decisions = await response.json();
          if (decisions.length > 0) {
            // Transform API data to feed entry format
            const transformed = decisions.map(d => {
              const time = d.created_at
                ? new Date(d.created_at).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: true })
                : '—';

              return {
                action: d.action,
                ticker: d.ticker || '—',
                detail: d.quantity
                  ? `${d.quantity} shares`
                  : (d.action === 'hold' ? 'No action taken' : '—'),
                time,
                reasoning: d.reasoning || '—',
                confidence: Math.round((d.confidence || 0) * 100),
                stats: [
                  d.position_size_pct != null
                    ? { label: 'Position size', value: `${(d.position_size_pct * 100).toFixed(1)}%`, highlight: null }
                    : null,
                  d.stop_loss_price
                    ? { label: 'Stop loss', value: `₹${d.stop_loss_price.toLocaleString('en-IN')}`, highlight: 'var(--dn)' }
                    : null,
                  d.guardrail_status === 'blocked'
                    ? { label: 'Guardrail', value: 'Blocked', highlight: 'var(--dn)' }
                    : null,
                ].filter(Boolean),
                status: d.guardrail_status === 'blocked'
                  ? `⛔ ${d.guardrail_reason || 'Blocked'}`
                  : (d.action !== 'hold' ? '✓ Executed' : null),
              };
            });
            setFeed(transformed);
            setHasRealData(true);
          }
        }
      } catch {
        // Use demo data
      }
    };
    fetchDecisions();
  }, []);

  return (
    <div>
      {/* Header */}
      <div style={{
        padding: '18px 20px',
        borderBottom: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', gap: '12px'
      }}>
        <div style={{
          width: '28px', height: '28px', borderRadius: '50%',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: '10px', fontWeight: 600,
          background: 'var(--blue-dim)', border: '1px solid #60a5fa22',
          color: 'var(--blue)'
        }}>
          AB
        </div>
        <div>
          <div style={{ fontSize: '14px', fontWeight: 500, letterSpacing: '-0.3px' }}>
            ArenaBot-1
            <span style={{
              fontSize: '9px', color: 'var(--blue)',
              background: 'var(--blue-dim)', border: '1px solid #60a5fa20',
              padding: '1px 5px', borderRadius: '2px', marginLeft: '8px'
            }}>
              Gemini
            </span>
            {!hasRealData && (
              <span style={{
                fontSize: '9px', color: 'var(--text3)',
                background: 'var(--ink3)', border: '1px solid var(--border)',
                padding: '1px 5px', borderRadius: '2px', marginLeft: '6px'
              }}>
                demo
              </span>
            )}
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text3)', marginTop: '2px' }}>
            {hasRealData
              ? `${feed.length} decisions logged`
              : 'Rank #2 · Score 764 · 26 trades this season'}
          </div>
        </div>
        <div style={{
          marginLeft: 'auto', display: 'flex', gap: '16px'
        }}>
          <div style={{ textAlign: 'right' }}>
            <div style={{
              fontSize: '10px', color: 'var(--text3)',
              textTransform: 'uppercase', letterSpacing: '.06em'
            }}>
              Return
            </div>
            <div style={{
              fontFamily: 'DM Mono, monospace', fontSize: '14px',
              fontWeight: 300, color: 'var(--up)'
            }}>
              +6.2%
            </div>
          </div>
          <div style={{ textAlign: 'right' }}>
            <div style={{
              fontSize: '10px', color: 'var(--text3)',
              textTransform: 'uppercase', letterSpacing: '.06em'
            }}>
              Score
            </div>
            <div style={{
              fontFamily: 'DM Mono, monospace', fontSize: '14px',
              fontWeight: 300, color: 'var(--blue)'
            }}>
              764
            </div>
          </div>
        </div>
      </div>

      {/* Feed entries */}
      <div style={{ padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
        {feed.map((entry, i) => (
          <AIFeedEntry key={i} {...entry} />
        ))}
      </div>
    </div>
  );
}
