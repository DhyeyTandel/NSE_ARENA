# engine/order_book.py
"""Standalone price-time-priority order book (SortedDict-backed, per-ticker
asyncio.Lock, partial fills). NOT wired into the live trade path — the
running app fills trades immediately at the current market quote via
services/trading.py, called from api/routes/trades.py and ai/execution.py.
This module is a self-contained order-matching exercise; see
engine/matching.py's docstring and README.md for the full picture."""
import itertools
from sortedcontainers import SortedDict
import asyncio
from .models import Order, Trade, OrderSide, OrderType


class OrderBook:
    def __init__(self, ticker: str):
        self.ticker = ticker
        self.lock = asyncio.Lock()
        # Tie-breaker for the sort key: two orders at the same price with
        # an identical (microsecond-resolution) timestamp would otherwise
        # collide on the same dict key and silently overwrite each other,
        # losing an order with no error. A monotonic sequence number makes
        # every key unique while still sorting later arrivals after
        # earlier ones at the same price, preserving price-time priority.
        self._seq = itertools.count()
        # Bids: key = (-price, timestamp, seq) — highest price first
        self.bids: SortedDict = SortedDict()
        # Asks: key = (price, timestamp, seq) — lowest price first
        self.asks: SortedDict = SortedDict()

    async def add_order(self, order: Order) -> list[Trade]:
        async with self.lock:  # CRITICAL: only one order at a time
            if order.side == OrderSide.BUY:
                trades = self._match_buy(order)
                if order.filled_quantity < order.quantity:
                    if order.order_type == OrderType.LIMIT:
                        key = (-order.limit_price, order.timestamp.isoformat(), next(self._seq))
                        self.bids[key] = order
            else:
                trades = self._match_sell(order)
                if order.filled_quantity < order.quantity:
                    if order.order_type == OrderType.LIMIT:
                        key = (order.limit_price, order.timestamp.isoformat(), next(self._seq))
                        self.asks[key] = order
            return trades

    def _next_match(self, resting_side: SortedDict, incoming_order: Order, is_buy: bool):
        """Walk `resting_side` in price-time priority order and return the
        (key, order) of the first resting order that both satisfies the
        incoming order's limit price (if any) and isn't a self-trade
        (same user_id as the incoming order). Self-trades are skipped over
        — the resting order stays in the book for another user to match
        against — but a level past the limit-price boundary always stops
        the scan entirely, since every level beyond it is equally
        unmatchable regardless of who it belongs to."""
        for key, resting in resting_side.items():
            price = key[0] if is_buy else -key[0]
            if incoming_order.order_type == OrderType.LIMIT:
                if is_buy and incoming_order.limit_price < price:
                    return None
                if not is_buy and incoming_order.limit_price > price:
                    return None
            if resting.user_id == incoming_order.user_id:
                continue  # self-trade prevention
            return key, resting
        return None

    def _match_buy(self, buy_order: Order) -> list[Trade]:
        trades = []
        while buy_order.filled_quantity < buy_order.quantity:
            match = self._next_match(self.asks, buy_order, is_buy=True)
            if match is None:
                break
            best_key, best_ask = match
            ask_price = best_key[0]
            remaining = buy_order.quantity - buy_order.filled_quantity
            fill_qty = min(remaining, best_ask.quantity - best_ask.filled_quantity)
            buy_order.filled_quantity += fill_qty
            best_ask.filled_quantity += fill_qty
            trades.append(Trade(
                buy_order_id=buy_order.id,
                sell_order_id=best_ask.id,
                ticker=self.ticker,
                price=ask_price,
                quantity=fill_qty,
            ))
            if best_ask.filled_quantity >= best_ask.quantity:
                del self.asks[best_key]
        return trades

    def _match_sell(self, sell_order: Order) -> list[Trade]:
        trades = []
        while sell_order.filled_quantity < sell_order.quantity:
            match = self._next_match(self.bids, sell_order, is_buy=False)
            if match is None:
                break
            best_key, best_bid = match
            bid_price = -best_key[0]  # negated back to positive
            remaining = sell_order.quantity - sell_order.filled_quantity
            fill_qty = min(remaining, best_bid.quantity - best_bid.filled_quantity)
            sell_order.filled_quantity += fill_qty
            best_bid.filled_quantity += fill_qty
            trades.append(Trade(
                buy_order_id=best_bid.id,
                sell_order_id=sell_order.id,
                ticker=self.ticker,
                price=bid_price,
                quantity=fill_qty,
            ))
            if best_bid.filled_quantity >= best_bid.quantity:
                del self.bids[best_key]
        return trades
