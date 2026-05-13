// components/OrderPanel.jsx
import { useState, useEffect } from 'react';

export function OrderPanel({ defaultSymbol = 'RELIANCE', onSubmit, livePrice, authenticated = false }) {
  const [side, setSide] = useState('buy');
  const [symbol, setSymbol] = useState(defaultSymbol);
  const [price, setPrice] = useState(livePrice || 2847.30);
  const [qty, setQty] = useState(10);
  const [showFees, setShowFees] = useState(false);

  useEffect(() => {
    if (livePrice && livePrice > 0) {
      setPrice(livePrice);
    }
  }, [livePrice]);

  const tradeValue = price * qty;
  const stt = tradeValue * 0.001;
  const brokerage = Math.min(tradeValue * 0.0003, 20);
  const exchangeCharge = tradeValue * 0.0000345;
  const sebi = tradeValue * 0.000001;
  const gst = (stt + brokerage + exchangeCharge + sebi) * 0.18;
  const totalFees = stt + brokerage + exchangeCharge + sebi + gst;

  const inputStyle = {
    background: 'var(--ink)',
    border: '1px solid var(--border2)',
    borderRadius: 'var(--r)',
    padding: '10px 12px',
    color: 'var(--text)',
    fontSize: '13px',
    fontFamily: 'DM Mono, monospace',
    outline: 'none',
    width: '100%',
    transition: 'border-color 0.2s var(--ease), box-shadow 0.2s var(--ease)',
  };

  const handleSubmit = () => {
    if (onSubmit) {
      onSubmit({
        ticker: symbol,
        side,
        order_type: 'market',
        quantity: qty,
        limit_price: price,
      });
    }
  };

  const isBuy = side === 'buy';

  return (
    <div style={{
      padding: '20px 18px',
      display: 'flex', flexDirection: 'column', gap: '16px',
      animation: 'fadeIn 0.4s var(--ease)',
    }}>

      {/* Header */}
      <div style={{
        fontSize: '13px', fontWeight: 600, color: 'var(--text)',
        letterSpacing: '-0.2px',
        display: 'flex', alignItems: 'center', gap: '8px',
      }}>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="10"/>
          <path d="M16 8h-6a2 2 0 1 0 0 4h4a2 2 0 1 1 0 4H8"/>
          <path d="M12 18V6"/>
        </svg>
        Place Order
        <span style={{
          fontSize: '10px', fontWeight: 500,
          color: 'var(--text3)', background: 'var(--ink3)',
          padding: '2px 8px', borderRadius: 'var(--r4)',
          marginLeft: 'auto',
        }}>
          Market
        </span>
      </div>

      {/* Symbol input */}
      <input
        value={symbol}
        onChange={e => setSymbol(e.target.value.toUpperCase())}
        style={{
          ...inputStyle,
          fontSize: '22px', fontWeight: 500, fontFamily: 'Inter, sans-serif',
          letterSpacing: '-0.5px',
          border: 'none',
          borderBottom: '2px solid var(--border3)',
          borderRadius: 0,
          padding: '0 0 10px 0',
          background: 'none',
        }}
        placeholder="SYMBOL"
      />

      {/* Buy / Sell toggle */}
      <div style={{
        display: 'grid', gridTemplateColumns: '1fr 1fr',
        borderRadius: 'var(--r)',
        overflow: 'hidden',
        border: '1px solid var(--border2)',
      }}>
        {['buy', 'sell'].map(s => (
          <button key={s} onClick={() => setSide(s)}
            style={{
              padding: '10px', fontSize: '12px', fontWeight: 600,
              letterSpacing: '.06em', textTransform: 'uppercase',
              cursor: 'pointer', border: 'none',
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px',
              background: side === s
                ? (s === 'buy' ? 'var(--up)' : 'var(--dn)')
                : 'var(--ink3)',
              color: side === s
                ? '#000'
                : 'var(--text3)',
              transition: 'all 0.2s var(--ease)',
            }}>
            {s === 'buy' ? '↑' : '↓'} {s}
          </button>
        ))}
      </div>

      {/* Fields */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
        {[
          { label: 'Price ₹', value: price, setter: setPrice },
          { label: 'Quantity', value: qty, setter: setQty }
        ].map(({ label, value, setter }) => (
          <div key={label} style={{ display: 'flex', flexDirection: 'column', gap: '5px' }}>
            <label style={{
              fontSize: '11px', fontWeight: 500, color: 'var(--text3)',
              textTransform: 'uppercase', letterSpacing: '.08em',
            }}>
              {label}
            </label>
            <input
              type="number"
              value={value}
              onChange={e => setter(parseFloat(e.target.value) || 0)}
              style={inputStyle}
              onFocus={e => {
                e.target.style.borderColor = isBuy ? 'var(--up-glow)' : 'var(--dn-glow)';
                e.target.style.boxShadow = `0 0 0 3px ${isBuy ? 'var(--up-dim)' : 'var(--dn-dim)'}`;
              }}
              onBlur={e => {
                e.target.style.borderColor = 'var(--border2)';
                e.target.style.boxShadow = 'none';
              }}
            />
          </div>
        ))}
      </div>

      {/* Trade value */}
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        padding: '10px 14px',
        background: 'var(--ink)', borderRadius: 'var(--r)',
        border: '1px solid var(--border)',
      }}>
        <span style={{ fontSize: '12px', color: 'var(--text3)' }}>Trade value</span>
        <span style={{
          fontFamily: 'DM Mono, monospace', fontSize: '14px',
          fontWeight: 500, color: 'var(--text)',
        }}>
          ₹{Math.round(tradeValue).toLocaleString('en-IN')}
        </span>
      </div>

      {/* Fee breakdown — collapsible */}
      <div>
        <button
          onClick={() => setShowFees(!showFees)}
          style={{
            width: '100%', padding: '8px 12px',
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            background: 'none', border: 'none',
            fontSize: '11px', color: 'var(--text3)',
            cursor: 'pointer',
          }}
        >
          <span>Charges & taxes</span>
          <span style={{
            display: 'flex', alignItems: 'center', gap: '4px',
            fontFamily: 'DM Mono, monospace',
          }}>
            ₹{totalFees.toFixed(2)}
            <svg
              width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
              style={{
                transform: showFees ? 'rotate(180deg)' : 'rotate(0deg)',
                transition: 'transform 0.2s var(--ease)',
              }}
            >
              <polyline points="6 9 12 15 18 9"/>
            </svg>
          </span>
        </button>
        {showFees && (
          <div style={{
            padding: '8px 12px',
            background: 'var(--ink)', borderRadius: 'var(--r)',
            border: '1px solid var(--border)',
            animation: 'fadeIn 0.2s var(--ease)',
          }}>
            {[
              { label: 'STT', value: `₹${stt.toFixed(2)}` },
              { label: 'Brokerage', value: `₹${brokerage.toFixed(2)}` },
              { label: 'Exchange charges', value: `₹${exchangeCharge.toFixed(2)}` },
              { label: 'GST', value: `₹${gst.toFixed(2)}` },
            ].map(({ label, value }) => (
              <div key={label} style={{
                display: 'flex', justifyContent: 'space-between',
                fontSize: '11px', fontFamily: 'DM Mono, monospace',
                color: 'var(--text3)', marginBottom: '3px',
              }}>
                <span>{label}</span><span>{value}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Submit */}
      <button
        onClick={handleSubmit}
        disabled={!authenticated}
        style={{
          width: '100%', padding: '12px', borderRadius: 'var(--r)',
          border: 'none', fontSize: '13px', fontWeight: 600,
          letterSpacing: '.04em', textTransform: 'uppercase',
          cursor: authenticated ? 'pointer' : 'not-allowed',
          background: !authenticated ? 'var(--ink3)'
            : isBuy
              ? 'linear-gradient(135deg, var(--up) 0%, #1ab370 100%)'
              : 'linear-gradient(135deg, var(--dn) 0%, #d63030 100%)',
          color: !authenticated ? 'var(--text3)' : '#000',
          transition: 'all 0.2s var(--ease)',
          opacity: authenticated ? 1 : 0.6,
          boxShadow: authenticated
            ? (isBuy ? '0 4px 16px var(--up-dim)' : '0 4px 16px var(--dn-dim)')
            : 'none',
        }}
        onMouseEnter={e => {
          if (authenticated) e.target.style.transform = 'translateY(-1px)';
        }}
        onMouseLeave={e => {
          if (authenticated) e.target.style.transform = 'translateY(0)';
        }}
      >
        {authenticated
          ? (isBuy ? '↑ Buy' : '↓ Sell') + ' ' + symbol
          : '🔒 Sign in to trade'}
      </button>
    </div>
  );
}
