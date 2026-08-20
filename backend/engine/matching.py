# engine/matching.py
"""Central matching engine managing per-ticker order books.

STANDALONE — NOT WIRED INTO THE LIVE APP. This module and order_book.py
are a self-contained price-time-priority matching engine (SortedDict order
books, per-ticker asyncio.Lock, partial fills) built as an order-matching
design exercise. Nothing in api/ or main.py imports it: the running app
fills trades immediately at the current market quote instead of resting
orders on a book — see services/trading.py (called from
api/routes/trades.py for human orders and ai/execution.py for AI agent
orders), which documents why in its own module docstring. If you're
looking for "the engine powering trades," that's it, not this.
"""
from .order_book import OrderBook
from .models import Order, Trade


class MatchingEngine:
    """Central matching engine managing per-ticker order books"""

    def __init__(self):
        self.order_books: dict[str, OrderBook] = {}

    def _get_order_book(self, ticker: str) -> OrderBook:
        if ticker not in self.order_books:
            self.order_books[ticker] = OrderBook(ticker)
        return self.order_books[ticker]

    async def submit(self, order: Order) -> list[Trade]:
        """Submit an order to the matching engine"""
        book = self._get_order_book(order.ticker)
        trades = await book.add_order(order)
        return trades

    def get_order_book_snapshot(self, ticker: str) -> dict:
        """Get current order book state for a ticker"""
        if ticker not in self.order_books:
            return {"bids": [], "asks": []}

        book = self.order_books[ticker]
        bids = []
        for key, order in book.bids.items():
            bids.append({
                "price": -key[0],
                "quantity": order.quantity - order.filled_quantity,
            })

        asks = []
        for key, order in book.asks.items():
            asks.append({
                "price": key[0],
                "quantity": order.quantity - order.filled_quantity,
            })

        return {"bids": bids, "asks": asks}
