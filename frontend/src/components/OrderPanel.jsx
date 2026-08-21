// components/OrderPanel.jsx
import { useState, useEffect } from 'react';

export function OrderPanel({ defaultSymbol = 'RELIANCE', onSubmit, livePrice, authenticated = false, cashBalance = 100000 }) {
  const [side, setSide] = useState('buy');
  const [symbol, setSymbol] = useState(defaultSymbol);
  const [price, setPrice] = useState(livePrice || 2891.45);
  const [qty, setQty] = useState(5);
  const [orderType, setOrderType] = useState('market');

  useEffect(() => { if (livePrice && livePrice > 0) setPrice(livePrice); }, [livePrice]);
  useEffect(() => { setSymbol(defaultSymbol); }, [defaultSymbol]);

  const est = price * qty;
  const cashAfter = side === 'buy' ? cashBalance - est : cashBalance + est;
  const isBuy = side === 'buy';
  const inr = n => '₹' + Math.round(Math.abs(n)).toLocaleString('en-IN');

  const handleSubmit = () => {
    if (onSubmit) {
      onSubmit({ ticker: symbol, side, order_type: orderType, quantity: qty, limit_price: price });
    }
  };

  return (
    <div style={{
      padding: '20px 22px', display: 'flex', flexDirection: 'column', gap: '14px',
      animation: 'fadeIn 0.4s var(--ease-swift)',
    }}>
      {/* Header */}
      <div className="t-eyebrow">Place order</div>

      {/* Buy / Sell pill toggle */}
      <div style={{
        display: 'grid', gridTemplateColumns: '1fr 1fr',
        background: 'var(--faint-soft)', borderRadius: '999px', padding: '3px',
      }}>
        {['buy', 'sell'].map(s => (
          <button key={s} onClick={() => setSide(s)} style={{
            border: 'none', cursor: 'pointer', padding: '8px 0',
            borderRadius: '999px', fontFamily: 'inherit',
            fontSize: '14px', fontWeight: 600,
            background: side === s ? 'var(--card)' : 'transparent',
            color: side === s ? 'var(--ink)' : 'var(--muted)',
            transition: 'all var(--dur-fast) var(--ease-swift)',
          }}>
            {s.charAt(0).toUpperCase() + s.slice(1)}
          </button>
        ))}
      </div>

      {/* Quantity */}
      <div>
        <div style={{ fontSize: '12.5px', fontWeight: 560, color: 'var(--muted)', marginBottom: '6px' }}>
          Quantity
        </div>
        <div style={{
          display: 'flex', alignItems: 'center',
          border: '1px solid var(--faint)', borderRadius: 'var(--r-input)',
          background: 'var(--card)', overflow: 'hidden',
        }}>
          <button onClick={() => setQty(Math.max(1, qty - 1))} style={{
            border: 'none', cursor: 'pointer', background: 'none',
            padding: '10px 14px', fontSize: '16px', color: 'var(--muted)',
            fontFamily: 'inherit',
          }}>−</button>
          <div style={{
            flex: 1, textAlign: 'center',
            fontFamily: '"JetBrains Mono", monospace', fontSize: '16px', fontWeight: 500,
          }}>{qty}</div>
          <button onClick={() => setQty(qty + 1)} style={{
            border: 'none', cursor: 'pointer', background: 'none',
            padding: '10px 14px', fontSize: '16px', color: 'var(--muted)',
            fontFamily: 'inherit',
          }}>+</button>
        </div>
      </div>

      {/* Order type */}
      <div>
        <div style={{ fontSize: '12.5px', fontWeight: 560, color: 'var(--muted)', marginBottom: '6px' }}>
          Order type
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          {['market', 'limit'].map(t => (
            <button key={t} onClick={() => setOrderType(t)} style={{
              flex: 1, cursor: 'pointer', padding: '8px 0',
              borderRadius: 'var(--r-input)', fontFamily: 'inherit',
              fontSize: '13.5px', fontWeight: 560,
              border: `1px solid ${orderType === t ? 'var(--ink)' : 'var(--faint)'}`,
              background: orderType === t ? 'var(--card)' : 'transparent',
              color: 'var(--ink)',
              transition: 'all var(--dur-fast) var(--ease-swift)',
            }}>
              {t.charAt(0).toUpperCase() + t.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {/* Summary */}
      <div style={{
        borderTop: '1px solid var(--faint)', paddingTop: '12px',
        display: 'flex', flexDirection: 'column', gap: '7px', fontSize: '13.5px',
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <span style={{ color: 'var(--muted)' }}>Est. {side} value</span>
          <span className="t-mono" style={{ fontWeight: 500 }}>{inr(est)}</span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <span style={{ color: 'var(--muted)' }}>Cash after</span>
          <span className="t-mono" style={{ fontWeight: 500 }}>{inr(cashAfter)}</span>
        </div>
      </div>

      {/* CTA */}
      <button
        onClick={handleSubmit}
        disabled={!authenticated}
        style={{
          border: 'none', cursor: authenticated ? 'pointer' : 'not-allowed',
          padding: '13px 0', borderRadius: '999px',
          background: !authenticated ? 'var(--faint-soft)'
            : isBuy ? 'var(--accent)' : 'var(--ink)',
          color: !authenticated ? 'var(--muted)' : 'var(--paper-lift)',
          fontFamily: 'inherit', fontSize: '15px', fontWeight: 600,
          transition: 'all var(--dur-fast) var(--ease-spring)',
          opacity: authenticated ? 1 : 0.6,
        }}
        onMouseEnter={e => { if (authenticated) e.currentTarget.style.transform = 'translateY(-2px)'; }}
        onMouseLeave={e => { if (authenticated) e.currentTarget.style.transform = 'translateY(0)'; }}
        onMouseDown={e => { if (authenticated) e.currentTarget.style.transform = 'scale(0.97)'; }}
        onMouseUp={e => { if (authenticated) e.currentTarget.style.transform = 'translateY(-2px)'; }}
      >
        {authenticated
          ? `${isBuy ? 'Buy' : 'Sell'} ${qty} ${symbol}`
          : 'Sign in to trade'}
      </button>

      <div style={{ fontSize: '12px', color: 'var(--muted-soft)', textAlign: 'center' }}>
        {orderType === 'market' ? 'Fills at market open price' : 'Good till cancelled'}
      </div>
    </div>
  );
}
