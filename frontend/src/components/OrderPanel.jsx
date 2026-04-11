// components/OrderPanel.jsx
import { useState, useEffect } from 'react';

export function OrderPanel({ defaultSymbol = 'RELIANCE', onSubmit, livePrice, authenticated = false }) {
  const [side, setSide] = useState('buy');
  const [symbol, setSymbol] = useState(defaultSymbol);
  const [price, setPrice] = useState(livePrice || 2847.30);
  const [qty, setQty] = useState(10);

  // Update price when live data arrives
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
    background: 'var(--ink2)', border: '1px solid var(--border2)',
    borderRadius: 'var(--r)', padding: '7px 9px', color: 'var(--text)',
    fontSize: '12px', fontFamily: 'DM Mono, monospace',
    outline: 'none', width: '100%'
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

  return (
    <div style={{ padding: '18px 16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>

      {/* Symbol input */}
      <input
        value={symbol}
        onChange={e => setSymbol(e.target.value.toUpperCase())}
        style={{
          ...inputStyle, fontSize: '20px', fontWeight: 300,
          letterSpacing: '-.5px', border: 'none', borderBottom: '1px solid var(--border3)',
          borderRadius: 0, padding: '0 0 8px 0', background: 'none'
        }}
        placeholder="SYMBOL"
      />

      {/* Buy / Sell toggle */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr',
        border: '1px solid var(--border2)', borderRadius: 'var(--r)', overflow: 'hidden' }}>
        {['buy', 'sell'].map(s => (
          <button key={s} onClick={() => setSide(s)}
            style={{
              padding: '8px', fontSize: '11px', fontWeight: 500,
              letterSpacing: '.04em', textTransform: 'uppercase',
              cursor: 'pointer', border: 'none', fontFamily: 'Geist, sans-serif',
              background: side === s
                ? (s === 'buy' ? 'var(--up)' : 'var(--dn)')
                : 'none',
              color: side === s
                ? (s === 'buy' ? '#000' : '#fff')
                : 'var(--text3)',
              transition: '.12s'
            }}>
            {s}
          </button>
        ))}
      </div>

      {/* Fields */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
        {[
          { label: 'Price ₹', value: price, setter: setPrice, type: 'number' },
          { label: 'Qty', value: qty, setter: setQty, type: 'number' }
        ].map(({ label, value, setter, type }) => (
          <div key={label} style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <label style={{ fontSize: '10px', color: 'var(--text3)',
              textTransform: 'uppercase', letterSpacing: '.06em' }}>
              {label}
            </label>
            <input type={type} value={value}
              onChange={e => setter(parseFloat(e.target.value) || 0)}
              style={inputStyle} />
          </div>
        ))}
      </div>

      {/* Fee breakdown */}
      <div style={{ background: 'var(--ink2)', borderRadius: 'var(--r)',
        padding: '10px 12px', border: '1px solid var(--border)' }}>
        {[
          { label: 'Trade value', value: `₹${Math.round(tradeValue).toLocaleString('en-IN')}` },
          { label: 'STT', value: `₹${stt.toFixed(2)}` },
          { label: 'Brokerage + GST', value: `₹${(brokerage + exchangeCharge + sebi + gst).toFixed(2)}` },
          { label: 'Total charges', value: `₹${totalFees.toFixed(2)}`, strong: true },
        ].map(({ label, value, strong }) => (
          <div key={label} style={{
            display: 'flex', justifyContent: 'space-between',
            fontSize: '11px', fontFamily: 'DM Mono, monospace',
            color: strong ? 'var(--text2)' : 'var(--text3)',
            marginBottom: strong ? 0 : '4px',
            paddingTop: strong ? '6px' : 0,
            borderTop: strong ? '1px solid var(--border)' : 'none'
          }}>
            <span>{label}</span><span>{value}</span>
          </div>
        ))}
      </div>

      {/* Submit */}
      <button onClick={handleSubmit} disabled={!authenticated} style={{
        width: '100%', padding: '10px', borderRadius: 'var(--r)',
        border: 'none', fontSize: '12px', fontWeight: 500,
        letterSpacing: '.04em', textTransform: 'uppercase',
        cursor: authenticated ? 'pointer' : 'not-allowed',
        fontFamily: 'Geist, sans-serif',
        background: !authenticated ? 'var(--ink3)'
          : side === 'buy' ? 'var(--up)' : 'var(--dn)',
        color: !authenticated ? 'var(--text3)'
          : side === 'buy' ? '#000' : '#fff',
        transition: '.12s',
        opacity: authenticated ? 1 : 0.7,
      }}>
        {authenticated
          ? (side === 'buy' ? 'Buy' : 'Sell') + ' ' + symbol
          : 'Login to trade'}
      </button>
    </div>
  );
}
