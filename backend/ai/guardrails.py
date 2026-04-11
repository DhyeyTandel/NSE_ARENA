# ai/guardrails.py
from dataclasses import dataclass


@dataclass
class GuardrailResult:
    approved: bool
    reason: str = ""


class RiskGuardrail:
    """Hard limits the AI cannot override"""

    MAX_POSITION_PCT = 0.20       # Never risk more than 20% of capital on a single position
    MAX_DRAWDOWN_PCT = -0.15      # Kill switch: trading halted if drawdown exceeds -15%
    REQUIRE_STOP_LOSS = True      # Stop loss is MANDATORY on every trade

    def validate(self, decision: dict, portfolio) -> GuardrailResult:
        """
        Validate an AI decision against hard guardrails.
        Returns GuardrailResult with approved=False if any rule is violated.
        """
        action = decision.get("action", "hold")

        if action == "hold":
            return GuardrailResult(approved=True)

        # Check drawdown kill switch
        current_value = portfolio.get("current_value", 0)
        starting_capital = portfolio.get("starting_capital", 100000)
        if starting_capital > 0:
            drawdown = (current_value - starting_capital) / starting_capital
            if drawdown <= self.MAX_DRAWDOWN_PCT:
                return GuardrailResult(
                    approved=False,
                    reason=f"Kill switch activated: drawdown {drawdown:.1%} exceeds -15% limit. "
                           f"Trading halted until manual review."
                )

        # Check position size
        position_size_pct = decision.get("position_size_pct", 0)
        if position_size_pct > self.MAX_POSITION_PCT:
            return GuardrailResult(
                approved=False,
                reason=f"Position size {position_size_pct:.0%} exceeds 20% limit. "
                       f"Max allowed: ₹{current_value * self.MAX_POSITION_PCT:,.0f}"
            )

        # Check stop loss requirement
        if self.REQUIRE_STOP_LOSS and action in ("buy", "sell"):
            stop_loss = decision.get("stop_loss_price")
            if not stop_loss or stop_loss <= 0:
                return GuardrailResult(
                    approved=False,
                    reason="Stop loss is MANDATORY on every trade. "
                           "Provide a valid stop_loss_price."
                )

        return GuardrailResult(approved=True)
