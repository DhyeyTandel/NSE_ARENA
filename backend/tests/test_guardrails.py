# tests/test_guardrails.py
"""P1 audit fix: RiskGuardrail used to trust the LLM's self-reported
position_size_pct verbatim, and any action outside buy/sell/hold that
slipped past the (missing) check would fall through unrejected. Guardrails
now recompute position size from quantity x price / portfolio_value using
the same market_data the agent already fetched, and explicitly reject any
action outside {buy, sell, hold}.
"""
from ai.guardrails import RiskGuardrail

guardrail = RiskGuardrail()


def _portfolio(current_value=100000.0, starting_capital=100000.0):
    return {"current_value": current_value, "starting_capital": starting_capital}


class TestActionValidation:
    def test_unrecognized_action_rejected(self):
        decision = {"action": "short", "ticker": "RELIANCE", "quantity": 10}
        result = guardrail.validate(decision, _portfolio())
        assert not result.approved
        assert "short" in result.reason

    def test_hold_approved_without_market_data(self):
        """A hold decision needs no price lookup at all."""
        result = guardrail.validate({"action": "hold"}, _portfolio())
        assert result.approved


class TestPositionSizeRecompute:
    def test_lying_about_position_size_pct_does_not_help(self):
        """The LLM claims a tiny 1% position, but quantity x price is
        actually 50% of the portfolio — the guardrail must catch the real
        number, not the self-reported one."""
        decision = {
            "action": "buy", "ticker": "RELIANCE", "quantity": 50,
            "position_size_pct": 0.01,  # lie
            "stop_loss_price": 900.0,
        }
        market_data = {"RELIANCE": {"price": 1000.0}}  # 50 * 1000 = 50,000 = 50% of 100k
        result = guardrail.validate(decision, _portfolio(), market_data)
        assert not result.approved
        assert "exceeds 20%" in result.reason

    def test_honest_small_position_approved(self):
        decision = {
            "action": "buy", "ticker": "RELIANCE", "quantity": 5,
            "position_size_pct": 0.05,
            "stop_loss_price": 900.0,
        }
        market_data = {"RELIANCE": {"price": 1000.0}}  # 5 * 1000 = 5,000 = 5% of 100k
        result = guardrail.validate(decision, _portfolio(), market_data)
        assert result.approved

    def test_non_positive_quantity_rejected(self):
        """A hallucinated negative/zero quantity would otherwise sail past
        the position-size check (quantity x price <= 0 is never > the
        20% limit) and reach execute_validated_trade, which would hit
        TradeRecord's quantity > 0 CheckConstraint as an uncaught
        IntegrityError instead of a clean guardrail rejection."""
        market_data = {"RELIANCE": {"price": 1000.0}}
        for bad_quantity in (-5, 0):
            decision = {
                "action": "buy", "ticker": "RELIANCE", "quantity": bad_quantity,
                "stop_loss_price": 900.0,
            }
            result = guardrail.validate(decision, _portfolio(), market_data)
            assert not result.approved, f"quantity={bad_quantity} should be rejected"
            assert "quantity" in result.reason.lower()

    def test_missing_market_data_rejected_not_trusted(self):
        """No price available for the ticker -> cannot verify position
        size -> reject, rather than falling back to trusting the LLM."""
        decision = {
            "action": "buy", "ticker": "UNKNOWN", "quantity": 5,
            "position_size_pct": 0.01,
            "stop_loss_price": 900.0,
        }
        result = guardrail.validate(decision, _portfolio(), market_data={})
        assert not result.approved
        assert "no market price" in result.reason.lower() or "cannot verify" in result.reason.lower()


class TestStopLossStillRequired:
    def test_missing_stop_loss_still_rejected(self):
        decision = {
            "action": "buy", "ticker": "RELIANCE", "quantity": 5,
            "position_size_pct": 0.05,
        }
        market_data = {"RELIANCE": {"price": 1000.0}}
        result = guardrail.validate(decision, _portfolio(), market_data)
        assert not result.approved
        assert "stop loss" in result.reason.lower()
