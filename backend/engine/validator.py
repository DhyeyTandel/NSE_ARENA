# engine/validator.py
from datetime import datetime, time
import pytz
from .models import Order, OrderSide

IST = pytz.timezone("Asia/Kolkata")
MARKET_OPEN = time(9, 15)
MARKET_CLOSE = time(15, 30)


class InsufficientBalanceError(Exception):
    pass


class MarketClosedError(Exception):
    pass


class CircuitBreakerError(Exception):
    pass


class InsufficientSharesError(Exception):
    pass


class Validator:
    def validate(self, order: Order, balance: float, holdings: dict,
                 previous_close: float = None, market_price: float = 0.0) -> None:
        """
        Validate an order before it enters the matching engine.
        Raises specific exceptions on failure.
        market_price is the current market price, used for market orders
        where limit_price is 0.
        """
        self._check_market_hours()
        self._check_circuit_breaker(order, previous_close, market_price)
        if order.side == OrderSide.BUY:
            self._check_balance(order, balance, market_price)
        else:
            self._check_holdings(order, holdings)

    def _check_market_hours(self) -> None:
        """Reject orders outside 9:15 AM – 3:30 PM IST, Monday–Friday"""
        now = datetime.now(IST)
        if now.weekday() >= 5:  # Saturday=5, Sunday=6
            raise MarketClosedError("Market is closed on weekends")
        current_time = now.time()
        if current_time < MARKET_OPEN or current_time > MARKET_CLOSE:
            raise MarketClosedError(
                f"Market hours are 9:15 AM – 3:30 PM IST. Current time: {current_time.strftime('%H:%M')}"
            )

    def _check_circuit_breaker(self, order: Order, previous_close: float,
                               market_price: float = 0.0) -> None:
        """Reject orders ±10% from previous close"""
        if previous_close is None or previous_close == 0:
            return
        price = order.limit_price if order.limit_price > 0 else market_price
        if price <= 0:
            return
        upper = previous_close * 1.10
        lower = previous_close * 0.90
        if price > upper or price < lower:
            raise CircuitBreakerError(
                f"Price ₹{price} outside circuit breaker range "
                f"₹{lower:.2f} – ₹{upper:.2f} (±10% of previous close ₹{previous_close:.2f})"
            )

    def _check_balance(self, order: Order, balance: float,
                       market_price: float = 0.0) -> None:
        """Check if user has sufficient balance for a buy order"""
        price = order.limit_price if order.limit_price > 0 else market_price
        estimated_cost = price * order.quantity
        if estimated_cost > balance:
            raise InsufficientBalanceError(
                f"Insufficient balance. Required: ₹{estimated_cost:,.2f}, Available: ₹{balance:,.2f}"
            )

    def _check_holdings(self, order: Order, holdings: dict) -> None:
        """Check if user has sufficient shares for a sell order"""
        available = holdings.get(order.ticker, 0)
        if order.quantity > available:
            raise InsufficientSharesError(
                f"Insufficient shares of {order.ticker}. "
                f"Required: {order.quantity}, Available: {available}"
            )
