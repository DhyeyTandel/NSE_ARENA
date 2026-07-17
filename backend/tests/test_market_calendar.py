# tests/test_market_calendar.py
"""Item 8 (ANTIGRAVITY_NEXT.md): NSE holiday calendar.

Trades previously executed on Diwali, Holi, Republic Day, etc. —
Validator._check_market_hours only knew about weekends and the
09:15–15:30 window. market_calendar.py adds the verified NSE 2026
equity-segment holiday list, wired into the validator.
"""
from datetime import date, datetime
from unittest.mock import patch

import pytest
import pytz

from engine import market_calendar
from engine.market_calendar import is_trading_day, is_market_open
from engine.validator import Validator, MarketClosedError

IST = pytz.timezone("Asia/Kolkata")


def _freeze_validator_clock(frozen: datetime):
    p = patch("engine.validator.datetime")
    mock_dt = p.start()
    mock_dt.now.return_value = frozen
    mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
    return p


class TestIsTradingDay:
    def test_known_holiday_is_not_trading_day(self):
        assert not is_trading_day(date(2026, 10, 20))  # Dussehra, a Tuesday
        assert not is_trading_day(date(2026, 1, 26))   # Republic Day, a Monday
        assert not is_trading_day(date(2026, 3, 3))    # Holi, a Tuesday
        assert not is_trading_day(date(2026, 11, 10))  # Diwali-Balipratipada

    def test_weekend_is_not_trading_day(self):
        assert not is_trading_day(date(2026, 3, 15))  # Sunday
        assert not is_trading_day(date(2026, 3, 14))  # Saturday

    def test_normal_weekday_is_trading_day(self):
        assert is_trading_day(date(2026, 3, 16))  # Monday, no holiday

    def test_every_2026_holiday_is_a_weekday(self):
        """Weekend holidays should be omitted from the list — the weekend
        rule already covers them."""
        for d in market_calendar.NSE_HOLIDAYS:
            assert d.weekday() < 5, f"{d} is a weekend date; drop it from NSE_HOLIDAYS"


class TestIsMarketOpen:
    def test_closed_one_second_before_open(self):
        assert not is_market_open(IST.localize(datetime(2026, 3, 16, 9, 14, 59)))

    def test_open_exactly_at_0915(self):
        assert is_market_open(IST.localize(datetime(2026, 3, 16, 9, 15, 0)))

    def test_open_exactly_at_1530(self):
        assert is_market_open(IST.localize(datetime(2026, 3, 16, 15, 30, 0)))

    def test_closed_after_1530(self):
        assert not is_market_open(IST.localize(datetime(2026, 3, 16, 15, 31, 0)))

    def test_closed_during_market_hours_on_holiday(self):
        assert not is_market_open(IST.localize(datetime(2026, 10, 20, 10, 0)))  # Dussehra

    def test_naive_datetime_treated_as_ist(self):
        assert is_market_open(datetime(2026, 3, 16, 10, 0))


class TestValidatorHolidayWiring:
    def test_validator_rejects_trade_on_holiday(self):
        frozen = IST.localize(datetime(2026, 10, 20, 10, 0))  # Dussehra, mid-session
        p = _freeze_validator_clock(frozen)
        try:
            with pytest.raises(MarketClosedError, match="Dussehra"):
                Validator()._check_market_hours()
        finally:
            p.stop()

    def test_validator_rejects_trade_on_weekend(self):
        frozen = IST.localize(datetime(2026, 3, 15, 10, 0))  # Sunday
        p = _freeze_validator_clock(frozen)
        try:
            with pytest.raises(MarketClosedError, match="weekend"):
                Validator()._check_market_hours()
        finally:
            p.stop()

    def test_validator_rejects_at_091459(self):
        frozen = IST.localize(datetime(2026, 3, 16, 9, 14, 59))
        p = _freeze_validator_clock(frozen)
        try:
            with pytest.raises(MarketClosedError, match="Market hours"):
                Validator()._check_market_hours()
        finally:
            p.stop()

    def test_validator_allows_at_091500(self):
        frozen = IST.localize(datetime(2026, 3, 16, 9, 15, 0))
        p = _freeze_validator_clock(frozen)
        try:
            Validator()._check_market_hours()  # must not raise
        finally:
            p.stop()
