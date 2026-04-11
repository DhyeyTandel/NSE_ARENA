# tests/test_validator.py
"""Unit tests for Validator — market hours, circuit breakers, balance/holdings."""

import pytest
from unittest.mock import patch
from datetime import datetime
import pytz

from engine.validator import (
    Validator, MarketClosedError, CircuitBreakerError,
    InsufficientBalanceError, InsufficientSharesError,
)
from engine.models import Order, OrderSide, OrderType

IST = pytz.timezone("Asia/Kolkata")
validator = Validator()


def _make_order(side=OrderSide.BUY, limit_price=0.0, quantity=10, ticker="RELIANCE"):
    return Order(
        user_id="1", ticker=ticker, side=side,
        order_type=OrderType.LIMIT if limit_price > 0 else OrderType.MARKET,
        quantity=quantity, limit_price=limit_price,
    )


class TestMarketHours:
    def test_rejects_weekend(self):
        """Orders should be rejected on Saturday/Sunday."""
        # Saturday at 10:00 AM IST
        saturday = IST.localize(datetime(2026, 3, 14, 10, 0))
        with patch("engine.validator.datetime") as mock_dt:
            mock_dt.now.return_value = saturday
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            with pytest.raises(MarketClosedError, match="weekends"):
                validator._check_market_hours()

    def test_rejects_outside_hours(self):
        """Orders before 9:15 AM should be rejected."""
        # Monday at 8:00 AM IST
        early_monday = IST.localize(datetime(2026, 3, 16, 8, 0))
        with patch("engine.validator.datetime") as mock_dt:
            mock_dt.now.return_value = early_monday
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            with pytest.raises(MarketClosedError):
                validator._check_market_hours()

    def test_accepts_during_hours(self):
        """Orders during market hours should pass."""
        # Monday at 10:30 AM IST
        valid_time = IST.localize(datetime(2026, 3, 16, 10, 30))
        with patch("engine.validator.datetime") as mock_dt:
            mock_dt.now.return_value = valid_time
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            # Should not raise
            validator._check_market_hours()


class TestCircuitBreaker:
    def test_rejects_above_10pct(self):
        """Limit price > 110% of previous close should be rejected."""
        order = _make_order(limit_price=1150.0)  # 115% of 1000
        with pytest.raises(CircuitBreakerError, match="circuit breaker"):
            validator._check_circuit_breaker(order, previous_close=1000.0)

    def test_rejects_below_10pct(self):
        """Limit price < 90% of previous close should be rejected."""
        order = _make_order(limit_price=850.0)  # 85% of 1000
        with pytest.raises(CircuitBreakerError, match="circuit breaker"):
            validator._check_circuit_breaker(order, previous_close=1000.0)


class TestBalanceAndHoldings:
    def test_insufficient_balance_limit_order(self):
        """Limit buy order exceeding balance should be rejected."""
        order = _make_order(side=OrderSide.BUY, limit_price=500.0, quantity=100)
        # Cost = 50,000. Balance = 10,000 → insufficient
        with pytest.raises(InsufficientBalanceError, match="Insufficient balance"):
            validator._check_balance(order, balance=10000.0)

    def test_insufficient_balance_market_order(self):
        """Market buy order exceeding balance should be rejected via market_price."""
        order = _make_order(side=OrderSide.BUY, limit_price=0.0, quantity=100)
        # market_price=500 * 100 = 50,000 > 10,000 balance
        with pytest.raises(InsufficientBalanceError, match="Insufficient balance"):
            validator._check_balance(order, balance=10000.0, market_price=500.0)

    def test_insufficient_shares(self):
        """Sell order exceeding holdings should be rejected."""
        order = _make_order(side=OrderSide.SELL, quantity=50, ticker="TCS")
        with pytest.raises(InsufficientSharesError, match="Insufficient shares"):
            validator._check_holdings(order, holdings={"TCS": 10})
