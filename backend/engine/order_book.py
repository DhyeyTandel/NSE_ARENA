# engine/order_book.py
from sortedcontainers import SortedDict
import asyncio
from .models import Order, Trade, OrderSide, OrderType


class OrderBook:
    def __init__(self, ticker: str):
        self.ticker = ticker
        self.lock = asyncio.Lock()
        # Bids: key = (-price, timestamp) — highest price first
        self.bids: SortedDict = SortedDict()
        # Asks: key = (price, timestamp) — lowest price first
        self.asks: SortedDict = SortedDict()

    async def add_order(self, order: Order) -> list[Trade]:
        async with self.lock:  # CRITICAL: only one order at a time
            if order.side == OrderSide.BUY:
                trades = self._match_buy(order)
                if order.filled_quantity < order.quantity:
                    if order.order_type == OrderType.LIMIT:
                        key = (-order.limit_price, order.timestamp.isoformat())
                        self.bids[key] = order
            else:
                trades = self._match_sell(order)
                if order.filled_quantity < order.quantity:
                    if order.order_type == OrderType.LIMIT:
                        key = (order.limit_price, order.timestamp.isoformat())
                        self.asks[key] = order
            return trades

    def _match_buy(self, buy_order: Order) -> list[Trade]:
        trades = []
        while self.asks:
            remaining = buy_order.quantity - buy_order.filled_quantity
            if remaining == 0:
                break
            best_key, best_ask = next(iter(self.asks.items()))
            ask_price = best_key[0]
            # Limit order: only fill if ask price <= our limit
            if buy_order.order_type == OrderType.LIMIT:
                if buy_order.limit_price < ask_price:
                    break
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
        while self.bids:
            remaining = sell_order.quantity - sell_order.filled_quantity
            if remaining == 0:
                break
            best_key, best_bid = next(iter(self.bids.items()))
            bid_price = -best_key[0]  # negated back to positive
            if sell_order.order_type == OrderType.LIMIT:
                if sell_order.limit_price > bid_price:
                    break
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
