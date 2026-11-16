// components/OrderPanel.jsx
import { useState, useEffect } from 'react';

const inr = n => '₹' + Math.round(Math.abs(n)).toLocaleString('en-IN');
const px = n => '₹' + n.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export function OrderPanel({
  defaultSymbol = 'RELIANCE', onSubmit, livePrice, authenticated = false, cashBalance = 100000,
  side: sideProp, onSideChange,
}) {
  const [ownSide, setOwnSide] = useState('buy');
  const side = sideProp ?? ownSide;
  const setSide = onSideChange ?? setOwnSide;
  const [symbol, setSymbol] = useState(defaultSymbol);
  const [price, setPrice] = useState(livePrice || 0);
  const [qty, setQty] = useState(5);
  const [orderType, setOrderType] = useState('market');
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState('');

  useEffect(() => { if (livePrice && livePrice > 0) setPrice(livePrice); }, [livePrice]);
  useEffect(() => { setSymbol(defaultSymbol); setSubmitError(''); }, [defaultSymbol]);

  const hasPrice = price > 0;
  const est = price * qty;
  const cashAfter = side === 'buy' ? cashBalance - est : cashBalance + est;
  const isBuy = side === 'buy';
  const shortBy = isBuy && hasPrice && qty > 0 && est > cashBalance ? est - cashBalance : 0;

  // One inline message at a time, most blocking first.
  const problem = qty < 1 ? 'Enter a quantity of at least 1'
    : shortBy > 0 ? `Not enough cash: short by ${inr(shortBy)}`
    : '';
  const blocked = !authenticated || !!problem || submitting;

  const handleSubmit = async () => {
    if (!onSubmit || blocked) return;
    setSubmitError('');
    setSubmitting(true);
    try {
      const result = await onSubmit({
        ticker: symbol, side, order_type: orderType, quantity: qty, limit_price: price > 0 ? price : undefined,
      });
      if (result && result.ok === false) setSubmitError(result.error || 'Trade failed');
    } finally {
      setSubmitting(false);
    }
  };

  const onQtyInput = (e) => {
    const digits = e.target.value.replace(/\D/g, '').slice(0, 7);
    setQty(digits === '' ? 0 : parseInt(digits, 10));
    setSubmitError('');
  };

  return (
    <div className="panel order">
      <div className="order-side" role="tablist" aria-label="Order side">
        {['buy', 'sell'].map(sd => (
          <button
            key={sd} type="button" role="tab" aria-selected={side === sd}
            className={`order-tab ${sd}${side === sd ? ' is-active' : ''}`}
            onClick={() => setSide(sd)}
          >
            {sd.charAt(0).toUpperCase() + sd.slice(1)}
          </button>
        ))}
      </div>

      <div className="order-body">
        <div className="order-symbol">
          <span className="order-symbol-name">{symbol}</span>
          <span className="muted num">{hasPrice ? px(price) : 'Price unavailable'}</span>
        </div>

        <div>
          <label className="order-label" htmlFor="order-qty">Quantity</label>
          <div className="stepper">
            <button type="button" aria-label="Decrease quantity" disabled={qty <= 1}
              onClick={() => setQty(Math.max(1, qty - 1))}>−</button>
            <input
              id="order-qty" className="stepper-input" inputMode="numeric" autoComplete="off"
              value={qty === 0 ? '' : String(qty)} onChange={onQtyInput}
              aria-invalid={qty < 1 ? 'true' : undefined}
            />
            <button type="button" aria-label="Increase quantity" onClick={() => setQty(qty + 1)}>+</button>
          </div>
        </div>

        <div>
          <div className="order-label" id="order-type-label">Order type</div>
          <div className="seg seg--block" role="group" aria-labelledby="order-type-label">
            {['market', 'limit'].map(t => (
              <button key={t} type="button" aria-pressed={orderType === t}
                className={orderType === t ? 'is-active' : ''} onClick={() => setOrderType(t)}>
                {t.charAt(0).toUpperCase() + t.slice(1)}
              </button>
            ))}
          </div>
        </div>

        <div className="order-sum">
          <div>
            <span className="muted">Est. {side} value</span>
            <span className="num order-sum-val">{hasPrice && qty > 0 ? inr(est) : '—'}</span>
          </div>
          <div>
            <span className="muted">Cash after</span>
            <span className={`num order-sum-val${shortBy > 0 ? ' dn' : ''}`}>{hasPrice && qty > 0 ? (cashAfter < 0 ? '−' : '') + inr(cashAfter) : inr(cashBalance)}</span>
          </div>
        </div>

        {(problem || submitError) && authenticated && (
          <div className="order-error" role="alert">{submitError || problem}</div>
        )}

        <button
          type="button" onClick={handleSubmit} disabled={blocked}
          className={`btn btn--lg btn--block ${isBuy ? 'btn--buy' : 'btn--sell'}${submitting ? ' is-loading' : ''}`}
        >
          {submitting && <span className="spinner" aria-hidden="true" />}
          {!authenticated ? 'Sign in to trade' : submitting ? 'Placing order' : `${isBuy ? 'Buy' : 'Sell'} ${qty > 0 ? qty : ''} ${symbol}`}
        </button>

        <div className="order-note">
          {orderType === 'market' ? 'Fills at market open price' : 'Good till cancelled'}
        </div>
      </div>
    </div>
  );
}
