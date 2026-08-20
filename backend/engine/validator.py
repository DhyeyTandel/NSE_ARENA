# engine/validator.py
from datetime import datetime, time
from decimal import Decimal
import pytz
from .fee_engine import FeeEngine
from .models import Order, OrderSide
from . import market_calendar

IST = pytz.timezone("Asia/Kolkata")
MARKET_OPEN = time(9, 15)
MARKET_CLOSE = time(15, 30)


def _to_decimal(value) -> Decimal:
    """Coerce a float/int/str/Decimal into a Decimal via its string form.
    Callers on the live money path (services/trading.py) already pass
    Decimal; unit tests and any other caller may still pass plain floats —
    normalizing here means both work and all the arithmetic below is exact
    either way."""
    return value if isinstance(value, Decimal) else Decimal(str(value))


class InsufficientBalanceError(Exception):
    pass


class MarketClosedError(Exception):
    pass


class CircuitBreakerError(Exception):
    pass


class InsufficientSharesError(Exception):
    pass


class Validator:
    def __init__(self):
        self._fee_engine = FeeEngine()

    def validate(self, order: Order, balance: float, holdings: dict,
                 previous_close: float = None, market_price: float = 0.0,
                 strict: bool = False) -> None:
        """
        Validate an order before it enters the matching engine.
        Raises specific exceptions on failure.
        market_price is the current market price, used for market orders
        where limit_price is 0.
        strict=True refuses to silently skip the circuit breaker when
        previous_close is missing/zero — use this for the live trade path,
        where a cache entry without a reference price must not become a
        way to bypass the breaker. Other callers keep the default lenient
        behavior.
        """
        self._check_market_hours()
        self._check_circuit_breaker(order, previous_close, market_price, strict=strict)
        if order.side == OrderSide.BUY:
            self._check_balance(order, balance, market_price)
        else:
            self._check_holdings(order, holdings)

    def _check_market_hours(self) -> None:
        """Reject orders outside 9:15 AM – 3:30 PM IST, Monday–Friday,
        and on NSE holidays"""
        now = datetime.now(IST)
        if now.weekday() >= 5:  # Saturday=5, Sunday=6
            raise MarketClosedError("Market is closed on weekends")
        holiday = market_calendar.holiday_name(now.date())
        if holiday:
            raise MarketClosedError(f"Market is closed today: {holiday} (NSE holiday)")
        current_time = now.time()
        if current_time < MARKET_OPEN or current_time > MARKET_CLOSE:
            raise MarketClosedError(
                f"Market hours are 9:15 AM – 3:30 PM IST. Current time: {current_time.strftime('%H:%M')}"
            )

    def _check_circuit_breaker(self, order: Order, previous_close,
                               market_price=0.0, strict: bool = False) -> None:
        """Reject orders ±10% from previous close"""
        if previous_close is None or previous_close == 0:
            if strict:
                raise CircuitBreakerError(
                    "Reference price (previous close) unavailable — cannot verify circuit breaker"
                )
            return
        previous_close = _to_decimal(previous_close)
        price = _to_decimal(order.limit_price if order.limit_price > 0 else market_price)
        if price <= 0:
            return
        upper = previous_close * Decimal("1.10")
        lower = previous_close * Decimal("0.90")
        if price > upper or price < lower:
            raise CircuitBreakerError(
                f"Price ₹{price} outside circuit breaker range "
                f"₹{lower:.2f} – ₹{upper:.2f} (±10% of previous close ₹{previous_close:.2f})"
            )

    def _check_balance(self, order: Order, balance,
                       market_price=0.0) -> None:
        """Check if user has sufficient balance for a buy order, including
        the fees the trade will actually incur — an estimate that ignored
        fees could pass validation and then still fail the DB-layer
        guarded UPDATE on the real, fee-inclusive cost."""
        balance = _to_decimal(balance)
        price = _to_decimal(order.limit_price if order.limit_price > 0 else market_price)
        estimated_fees = self._fee_engine.calculate(
            price=price, quantity=order.quantity, side="buy", trade_type="delivery",
        ).total
        estimated_cost = price * order.quantity + estimated_fees
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
