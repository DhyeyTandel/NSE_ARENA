// components/OrderPanel.jsx
import { useState, useEffect } from 'react';

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

  useEffect(() => { if (livePrice && livePrice > 0) setPrice(livePrice); }, [livePrice]);
  useEffect(() => { setSymbol(defaultSymbol); }, [defaultSymbol]);

  const est = price * qty;
  const cashAfter = side === 'buy' ? cashBalance - est : cashBalance + est;
  const isBuy = side === 'buy';
  const inr = n => '₹' + Math.round(Math.abs(n)).toLocaleString('en-IN');

  const handleSubmit = () => {
    if (onSubmit) {
      onSubmit({ ticker: symbol, side, order_type: orderType, quantity: qty, limit_price: price > 0 ? price : undefined });
    }
  };

  return (
    <div className="panel order">
      <div className="order-tabs" role="tablist" aria-label="Order side">
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
        <div>
          <div className="order-label">Quantity</div>
          <div className="stepper">
            <button type="button" aria-label="Decrease quantity" onClick={() => setQty(Math.max(1, qty - 1))}>−</button>
            <output aria-label="Quantity">{qty}</output>
            <button type="button" aria-label="Increase quantity" onClick={() => setQty(qty + 1)}>+</button>
          </div>
        </div>

        <div>
          <div className="order-label">Order type</div>
          <div className="seg seg--block">
            {['market', 'limit'].map(t => (
              <button key={t} type="button" className={orderType === t ? 'is-active' : ''} onClick={() => setOrderType(t)}>
                {t.charAt(0).toUpperCase() + t.slice(1)}
              </button>
            ))}
          </div>
        </div>

        <div className="order-sum">
          <div>
            <span className="muted">Est. {side} value</span>
            <span style={{ fontWeight: 500 }}>{inr(est)}</span>
          </div>
          <div>
            <span className="muted">Cash after</span>
            <span style={{ fontWeight: 500 }}>{inr(cashAfter)}</span>
          </div>
        </div>

        <button
          type="button" onClick={handleSubmit} disabled={!authenticated}
          className={`btn btn--block ${isBuy ? 'btn--buy' : 'btn--sell'}`}
        >
          {authenticated ? `${isBuy ? 'Buy' : 'Sell'} ${qty} ${symbol}` : 'Sign in to trade'}
        </button>

        <div className="order-note">
          {orderType === 'market' ? 'Fills at market open price' : 'Good till cancelled'}
        </div>
      </div>
    </div>
  );
}
