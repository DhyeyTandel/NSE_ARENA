# tests/test_settlement.py
"""Unit tests for SettlementEngine — T+1 dates, position state transitions."""

from unittest.mock import patch
from datetime import datetime
import pytz

from engine.settlement import SettlementEngine, Position, PositionState

IST = pytz.timezone("Asia/Kolkata")
engine = SettlementEngine()


class TestSettlementDate:
    def test_next_trading_day_weekday(self):
        """Weekday trade → settlement is next day."""
        # Wednesday 2026-03-11 → Thursday 2026-03-12
        trade_date = IST.localize(datetime(2026, 3, 11, 10, 0))
        result = engine.calculate_settlement_date(trade_date)
        assert result == "2026-03-12"

    def test_skips_weekend(self):
        """Friday trade → settlement is Monday (skips Saturday/Sunday)."""
        # Friday 2026-03-13 → Monday 2026-03-16
        trade_date = IST.localize(datetime(2026, 3, 13, 14, 0))
        result = engine.calculate_settlement_date(trade_date)
        assert result == "2026-03-16"


class TestCreatePosition:
    def test_creates_pending_position(self):
        """New position should start in PENDING state."""
        trade_date = IST.localize(datetime(2026, 3, 11, 10, 0))
        pos = engine.create_pending_position("RELIANCE", 10, 2850.0, trade_date)
        assert pos.state == PositionState.PENDING
        assert pos.ticker == "RELIANCE"
        assert pos.quantity == 10
        assert pos.avg_price == 2850.0
        assert pos.settlement_date == "2026-03-12"


class TestSettlePositions:
    def test_confirms_ready_positions(self):
        """Pending positions should become confirmed after 6 PM on settlement date."""
        pos = Position(
            ticker="TCS", quantity=5, avg_price=3900.0,
            state=PositionState.PENDING, settlement_date="2026-03-12",
        )
        # Mock: it's 7 PM on 2026-03-12
        evening = IST.localize(datetime(2026, 3, 12, 19, 0))
        with patch("engine.settlement.datetime") as mock_dt:
            mock_dt.now.return_value = evening
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            settled = engine.settle_positions([pos])

        assert len(settled) == 1
        assert pos.state == PositionState.CONFIRMED


class TestAvailableQuantity:
    def test_only_confirmed_are_sellable(self):
        """Pending positions should not be included in available quantity."""
        positions = [
            Position(ticker="INFY", quantity=10, state=PositionState.CONFIRMED),
            Position(ticker="INFY", quantity=5, state=PositionState.PENDING),
            Position(ticker="TCS", quantity=20, state=PositionState.CONFIRMED),
        ]
        assert engine.get_available_quantity(positions, "INFY") == 10
        assert engine.get_total_quantity(positions, "INFY") == 15
