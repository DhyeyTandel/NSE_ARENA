# tests/test_fee_engine.py
"""Unit tests for FeeEngine — verify STT, brokerage, GST calculations."""

from decimal import Decimal

from engine.fee_engine import FeeEngine, FeeBreakdown

fee = FeeEngine()


class TestDeliveryFees:
    def test_delivery_stt_both_sides(self):
        """Delivery STT is 0.1% of trade value for both buy and sell."""
        buy = fee.calculate(price=1000.0, quantity=10, side="buy", trade_type="delivery")
        sell = fee.calculate(price=1000.0, quantity=10, side="sell", trade_type="delivery")
        # 0.1% of 10,000 = 10.0
        assert buy.stt == 10.0
        assert sell.stt == 10.0

    def test_brokerage_cap_at_20(self):
        """Brokerage is 0.03% of value, capped at ₹20."""
        # Trade value = 1,000,000 → 0.03% = 300 → capped at 20
        result = fee.calculate(price=10000.0, quantity=100, side="buy")
        assert result.brokerage == 20.0

    def test_gst_on_subtotal(self):
        """GST is 18% on (STT + brokerage + exchange + SEBI)."""
        result = fee.calculate(price=1000.0, quantity=10, side="buy")
        subtotal = result.stt + result.brokerage + result.exchange_charge + result.sebi_charge
        expected_gst = round(subtotal * Decimal("0.18"), 2)
        assert result.gst == expected_gst

    def test_all_fields_populated(self):
        """All 6 FeeBreakdown fields should be positive for a delivery trade."""
        result = fee.calculate(price=500.0, quantity=20, side="buy")
        assert result.stt > 0
        assert result.brokerage > 0
        assert result.exchange_charge > 0
        assert result.sebi_charge > 0
        assert result.gst > 0
        assert result.total > 0


class TestIntradayFees:
    def test_intraday_stt_sell_only(self):
        """Intraday STT: 0.025% on sell side, 0 on buy side."""
        buy = fee.calculate(price=1000.0, quantity=10, side="buy", trade_type="intraday")
        sell = fee.calculate(price=1000.0, quantity=10, side="sell", trade_type="intraday")
        assert buy.stt == 0.0
        # 0.025% of 10,000 = 2.5
        assert sell.stt == 2.5


class TestDecimalRounding:
    """P1 audit fix: money fields (engine/models.py, db/models.py) are now
    Decimal/Numeric end-to-end instead of float, closing the classic
    cent-level-drift risk. These cases pick prices that are exact in
    decimal but NOT exactly representable in binary float, where float
    arithmetic would visibly drift."""

    def test_fractional_price_rounds_exactly(self):
        """price=333.33 isn't exactly representable in binary float (same
        class of error as 0.1 + 0.2 != 0.3). Decimal(str(price)) must land
        on the exact decimal value, not a float-representable near-miss,
        so the rounded fee comes out exact rather than off by a paisa."""
        result = fee.calculate(price=333.33, quantity=3, side="buy", trade_type="delivery")
        # value = 999.99; stt = value * 0.001 = 0.99999 -> rounds to 1.00 exactly
        assert result.stt == Decimal("1.00")
        assert isinstance(result.stt, Decimal)

    def test_fee_breakdown_fields_are_decimal_not_float(self):
        result = fee.calculate(price=1000.0, quantity=10, side="buy")
        for field_name in ("stt", "brokerage", "exchange_charge", "sebi_charge", "gst", "total"):
            value = getattr(result, field_name)
            assert isinstance(value, Decimal), f"{field_name} should be Decimal, got {type(value)}"

    def test_calculate_accepts_decimal_price_without_error(self):
        """Callers on the live money path (services/trading.py) pass an
        already-Decimal price — calculate() must not choke on that."""
        result = fee.calculate(price=Decimal("1000.00"), quantity=10, side="buy")
        assert result.stt == Decimal("10.00")
