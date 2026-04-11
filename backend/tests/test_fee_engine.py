# tests/test_fee_engine.py
"""Unit tests for FeeEngine — verify STT, brokerage, GST calculations."""

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
        expected_gst = round(subtotal * 0.18, 2)
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
