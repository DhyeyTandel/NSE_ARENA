# ai/guardrails.py
from dataclasses import dataclass


@dataclass
class GuardrailResult:
    approved: bool
    reason: str = ""


class RiskGuardrail:
    """Hard limits the AI cannot override"""

    VALID_ACTIONS = ("buy", "sell", "hold")
    MAX_POSITION_PCT = 0.20       # Never risk more than 20% of capital on a single position
    MAX_DRAWDOWN_PCT = -0.15      # Kill switch: trading halted if drawdown exceeds -15%
    REQUIRE_STOP_LOSS = True      # Stop loss is MANDATORY on every trade

    def validate(self, decision: dict, portfolio, market_data: dict | None = None) -> GuardrailResult:
        """
        Validate an AI decision against hard guardrails.
        Returns GuardrailResult with approved=False if any rule is violated.

        `market_data` (the same watchlist quotes passed into run_cycle) is
        used to recompute position_size_pct from quantity x price /
        portfolio_value rather than trusting the LLM's self-reported
        value — a model can misreport (or lie about) its own position
        size, but it can't fake the arithmetic once we do it ourselves.
        """
        action = decision.get("action", "hold")

        if action not in self.VALID_ACTIONS:
            return GuardrailResult(
                approved=False,
                reason=f"Unrecognized action {action!r} — must be one of {self.VALID_ACTIONS}.",
            )

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

        # Check position size — recomputed from quantity x price, not
        # trusted from decision["position_size_pct"].
        ticker = decision.get("ticker")
        quantity = decision.get("quantity", 0) or 0
        if quantity <= 0:
            # A non-positive quantity would otherwise sail through the
            # position-size check below (quantity * price <= 0 is never
            # > MAX_POSITION_PCT) and reach execute_validated_trade, which
            # would hit TradeRecord's quantity > 0 CheckConstraint as an
            # uncaught IntegrityError instead of a clean rejection here.
            return GuardrailResult(
                approved=False,
                reason=f"Invalid quantity {quantity!r} — must be a positive integer.",
            )
        quote = (market_data or {}).get(ticker) or {}
        price = quote.get("price")
        if not price or price <= 0:
            return GuardrailResult(
                approved=False,
                reason=f"No market price available for {ticker!r} — cannot verify position size.",
            )
        position_size_pct = (quantity * price) / current_value if current_value > 0 else 0
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
