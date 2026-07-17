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
    background: 'var(--paper)',
    border: '1px solid var(--faint)',
    borderRadius: 'var(--r-input)',
    padding: '10px 12px',
    color: 'var(--ink)',
    fontSize: '13px',
    fontFamily: '"JetBrains Mono", monospace',
    outline: 'none',
    width: '100%',
    transition: `border-color var(--dur-fast) var(--ease-swift), box-shadow var(--dur-fast) var(--ease-swift)`,
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
      animation: 'fadeIn 0.4s var(--ease-swift)',
    }}>

      {/* Header */}
      <div style={{
        fontSize: '13px', fontWeight: 600, color: 'var(--ink)',
        letterSpacing: '-0.2px',
        display: 'flex', alignItems: 'center', gap: '8px',
      }}>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="10"/>
          <path d="M16 8h-6a2 2 0 1 0 0 4h4a2 2 0 1 1 0 4H8"/>
          <path d="M12 18V6"/>
        </svg>
        Place order
        <span style={{
          fontSize: '10px', fontWeight: 500,
          color: 'var(--muted)', background: 'var(--paper-lift)',
          padding: '2px 8px', borderRadius: 'var(--r-pill)',
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
          fontSize: '22px', fontWeight: 500, fontFamily: '"Sofia Sans", sans-serif',
          letterSpacing: '-0.02em',
          border: 'none',
          borderBottom: '2px solid var(--ink-soft)',
          borderRadius: 0,
          padding: '0 0 10px 0',
          background: 'none',
        }}
        placeholder="SYMBOL"
      />

      {/* Buy / Sell toggle */}
      <div style={{
        display: 'grid', gridTemplateColumns: '1fr 1fr',
        borderRadius: 'var(--r-input)',
        overflow: 'hidden',
        border: '1px solid var(--faint)',
      }}>
        {['buy', 'sell'].map(s => (
          <button key={s} onClick={() => setSide(s)}
            style={{
              padding: '10px', fontSize: '12px', fontWeight: 600,
              letterSpacing: '.06em', textTransform: 'uppercase',
              cursor: 'pointer', border: 'none',
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px',
              background: side === s
                ? (s === 'buy' ? 'var(--success)' : 'var(--error)')
                : 'var(--paper-lift)',
              color: side === s
                ? '#fff'
                : 'var(--muted)',
              transition: `all var(--dur-fast) var(--ease-swift)`,
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
            <label className="t-label">
              {label}
            </label>
            <input
              type="number"
              value={value}
              onChange={e => setter(parseFloat(e.target.value) || 0)}
              style={inputStyle}
              onFocus={e => {
                e.target.style.borderColor = isBuy ? 'var(--success-glow)' : 'var(--error-glow)';
                e.target.style.boxShadow = `0 0 0 3px ${isBuy ? 'var(--success-soft)' : 'var(--error-soft)'}`;
              }}
              onBlur={e => {
                e.target.style.borderColor = 'var(--faint)';
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
        background: 'var(--paper)', borderRadius: 'var(--r-input)',
        border: '1px solid var(--faint)',
      }}>
        <span style={{ fontSize: '12px', color: 'var(--muted)' }}>Trade value</span>
        <span style={{
          fontFamily: '"JetBrains Mono", monospace', fontSize: '14px',
          fontWeight: 500, color: 'var(--ink)',
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
            fontSize: '11px', color: 'var(--muted)',
            cursor: 'pointer',
          }}
        >
          <span>Charges & taxes</span>
          <span style={{
            display: 'flex', alignItems: 'center', gap: '4px',
            fontFamily: '"JetBrains Mono", monospace',
          }}>
            ₹{totalFees.toFixed(2)}
            <svg
              width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
              style={{
                transform: showFees ? 'rotate(180deg)' : 'rotate(0deg)',
                transition: `transform var(--dur-fast) var(--ease-swift)`,
              }}
            >
              <polyline points="6 9 12 15 18 9"/>
            </svg>
          </span>
        </button>
        {showFees && (
          <div style={{
            padding: '8px 12px',
            background: 'var(--paper)', borderRadius: 'var(--r-input)',
            border: '1px solid var(--faint)',
            animation: 'fadeIn 0.2s var(--ease-swift)',
          }}>
            {[
              { label: 'STT', value: `₹${stt.toFixed(2)}` },
              { label: 'Brokerage', value: `₹${brokerage.toFixed(2)}` },
              { label: 'Exchange charges', value: `₹${exchangeCharge.toFixed(2)}` },
              { label: 'GST', value: `₹${gst.toFixed(2)}` },
            ].map(({ label, value }) => (
              <div key={label} style={{
                display: 'flex', justifyContent: 'space-between',
                fontSize: '11px', fontFamily: '"JetBrains Mono", monospace',
                color: 'var(--muted)', marginBottom: '3px',
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
          width: '100%', padding: '13px', borderRadius: 'var(--r-pill)',
          border: 'none', fontSize: '13px', fontWeight: 600,
          letterSpacing: '.04em', textTransform: 'uppercase',
          cursor: authenticated ? 'pointer' : 'not-allowed',
          background: !authenticated ? 'var(--paper-lift)'
            : isBuy
              ? 'linear-gradient(135deg, var(--success) 0%, #156B45 100%)'
              : 'linear-gradient(135deg, var(--error) 0%, #A8281F 100%)',
          color: !authenticated ? 'var(--muted)' : '#fff',
          transition: `all var(--dur-fast) var(--ease-swift)`,
          opacity: authenticated ? 1 : 0.6,
          boxShadow: authenticated
            ? (isBuy ? '0 4px 16px var(--success-soft)' : '0 4px 16px var(--error-soft)')
            : 'none',
        }}
        onMouseEnter={e => {
          if (authenticated) e.target.style.transform = 'translateY(-2px)';
        }}
        onMouseLeave={e => {
          if (authenticated) e.target.style.transform = 'translateY(0)';
        }}
      >
        {authenticated
          ? (isBuy ? '↑ Buy' : '↓ Sell') + ' ' + symbol
          : 'Sign in to trade'}
      </button>
    </div>
  );
}
