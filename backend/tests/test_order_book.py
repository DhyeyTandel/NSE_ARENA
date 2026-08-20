# tests/test_order_book.py
"""P0 audit fix, engine/order_book.py (standalone matching-engine exercise,
not wired into the live trade path — see the module docstring):

1. Resting orders were keyed by (price, timestamp.isoformat()). Two orders
   at the same price with an identical microsecond timestamp collided on
   the same dict key and silently overwrote each other, losing an order
   with no error. A monotonic sequence number added to the key closes
   this.
2. _match_buy/_match_sell never compared user_id, so an order could trade
   against its own resting order on the same book. Self-trades are now
   skipped over (the resting order stays in the book for another user).
"""
from datetime import datetime

import pytest

from engine.models import Order, OrderSide, OrderType
from engine.order_book import OrderBook


def _limit_order(user_id: str, side: OrderSide, price: float, qty: int, ts: datetime) -> Order:
    return Order(
        user_id=user_id,
        ticker="RELIANCE",
        side=side,
        order_type=OrderType.LIMIT,
        quantity=qty,
        limit_price=price,
        timestamp=ts,
    )


@pytest.mark.asyncio
async def test_same_price_same_timestamp_orders_do_not_overwrite():
    """Two distinct resting asks at an identical price and identical
    (microsecond) timestamp must both survive in the book, not collide on
    the same dict key."""
    book = OrderBook("RELIANCE")
    same_ts = datetime(2026, 3, 16, 10, 0, 0, 123456)

    ask1 = _limit_order("seller_1", OrderSide.SELL, 1000.0, 10, same_ts)
    ask2 = _limit_order("seller_2", OrderSide.SELL, 1000.0, 10, same_ts)

    await book.add_order(ask1)
    await book.add_order(ask2)

    assert len(book.asks) == 2, "both resting asks must be present, not collided into one key"

    # A buy for the combined quantity should fill against both, price-time
    # priority meaning ask1 (inserted first) fills before ask2.
    buy = _limit_order("buyer_1", OrderSide.BUY, 1000.0, 20, same_ts)
    trades = book._match_buy(buy)

    assert len(trades) == 2
    assert trades[0].sell_order_id == ask1.id
    assert trades[1].sell_order_id == ask2.id
    assert sum(t.quantity for t in trades) == 20


@pytest.mark.asyncio
async def test_self_trade_is_skipped_not_matched():
    """A user's incoming buy must not match their own resting sell on the
    same book — it should skip past it and match the next eligible order,
    leaving the self-order resting untouched."""
    book = OrderBook("RELIANCE")
    t0 = datetime(2026, 3, 16, 10, 0, 0, 0)
    t1 = datetime(2026, 3, 16, 10, 0, 1, 0)

    own_ask = _limit_order("trader_x", OrderSide.SELL, 1000.0, 10, t0)
    other_ask = _limit_order("trader_y", OrderSide.SELL, 1000.0, 10, t1)

    await book.add_order(own_ask)
    await book.add_order(other_ask)

    incoming_buy = _limit_order("trader_x", OrderSide.BUY, 1000.0, 10, t1)
    trades = await book.add_order(incoming_buy)

    assert len(trades) == 1
    assert trades[0].sell_order_id == other_ask.id, "must match the other user's order, not its own"
    assert own_ask.filled_quantity == 0, "the self-order must remain untouched in the book"

    remaining_asks = list(book.asks.values())
    assert own_ask in remaining_asks


@pytest.mark.asyncio
async def test_self_trade_prevention_respects_limit_price_boundary():
    """Skipping a self-trade must not let matching reach past the incoming
    order's limit price — a self-trade at a bad price still stops the scan."""
    book = OrderBook("RELIANCE")
    t0 = datetime(2026, 3, 16, 10, 0, 0, 0)
    t1 = datetime(2026, 3, 16, 10, 0, 1, 0)

    # Own resting ask at 1000 (best price), another user's ask at 1100
    # (worse price, outside a buy limit of 1000).
    own_ask = _limit_order("trader_x", OrderSide.SELL, 1000.0, 10, t0)
    other_ask = _limit_order("trader_y", OrderSide.SELL, 1100.0, 10, t1)

    await book.add_order(own_ask)
    await book.add_order(other_ask)

    incoming_buy = _limit_order("trader_x", OrderSide.BUY, 1000.0, 10, t1)
    trades = await book.add_order(incoming_buy)

    assert trades == [], "no eligible counterparty within the limit price — must not fill"
