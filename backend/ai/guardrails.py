# ai/guardrails.py
import math
from dataclasses import dataclass

# Single source of truth for the AI account's risk rules. The model prompt
# (prompts.py, agent.py) reads these same values, so the text the model is
# shown and the limits the code enforces cannot drift apart.
MAX_POSITION_PCT = 0.20   # one ticker may never exceed 20% of total portfolio value
MAX_DRAWDOWN_PCT = -0.15  # kill switch: new AI decisions halted at -15% vs starting capital
STOP_LOSS_PCT = 0.08      # AI holdings down more than 8% from average buy price are sold in full


def pct_label(fraction: float) -> str:
    """0.2 -> '20%', 0.08 -> '8%' (for prompt/reason text)."""
    return f"{fraction * 100:g}%"


def _valid_price(quote) -> float | None:
    price = (quote or {}).get("price") if isinstance(quote, dict) else None
    try:
        price = float(price)
    except (TypeError, ValueError):
        return None
    return price if math.isfinite(price) and price > 0 else None


def find_stop_loss_breaches(positions: list[dict], market_data: dict,
                            stop_loss_pct: float = STOP_LOSS_PCT) -> list[dict]:
    """Holdings whose loss from average buy price exceeds `stop_loss_pct`.

    A holding with a missing, non-numeric, NaN or non-positive quote is
    skipped (no forced action on data we cannot trust); so is a holding
    with no usable average price or quantity.
    """
    breaches = []
    for p in positions:
        price = _valid_price(market_data.get(p.get("ticker")))
        avg = p.get("avg_price") or 0
        qty = p.get("quantity") or 0
        if price is None or avg <= 0 or qty <= 0:
            continue
        loss = (avg - price) / avg
        if loss > stop_loss_pct:
            breaches.append({
                "ticker": p["ticker"], "quantity": qty,
                "avg_price": avg, "price": price, "loss_pct": loss,
            })
    return breaches


@dataclass
class GuardrailResult:
    approved: bool
    reason: str = ""


class RiskGuardrail:
    """Hard limits the AI cannot override"""

    VALID_ACTIONS = ("buy", "sell", "hold")
    MAX_POSITION_PCT = MAX_POSITION_PCT
    MAX_DRAWDOWN_PCT = MAX_DRAWDOWN_PCT
    STOP_LOSS_PCT = STOP_LOSS_PCT
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
                    reason=f"Kill switch activated: drawdown {drawdown:.1%} exceeds {pct_label(self.MAX_DRAWDOWN_PCT)} limit. "
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
                reason=f"Position size {position_size_pct:.0%} exceeds {pct_label(self.MAX_POSITION_PCT)} limit. "
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

    def cap_buy_quantity(self, decision: dict, portfolio: dict,
                         market_data: dict | None) -> tuple[int, str]:
        """Aggregate position cap for a buy: existing holding value plus the
        new buy may not exceed MAX_POSITION_PCT of total portfolio value
        (cash + holdings; `portfolio["current_value"]`).

        Returns (allowed_quantity, note). allowed_quantity is the requested
        quantity if it fits, a smaller number if trimmed, or 0 if no room
        remains. `note` explains any trim/block and is "" when untouched.
        Non-buy decisions are returned unchanged. An unusable quote returns
        0 (a buy can never be sized without a price).
        """
        quantity = int(decision.get("quantity", 0) or 0)
        if decision.get("action") != "buy":
            return quantity, ""
        ticker = decision.get("ticker")
        price = _valid_price((market_data or {}).get(ticker))
        if price is None:
            return 0, f"No market price available for {ticker!r} - cannot size position cap."
        total_value = portfolio.get("current_value", 0) or 0
        existing_qty = sum(
            p.get("quantity", 0) or 0
            for p in portfolio.get("positions", [])
            if p.get("ticker") == ticker
        )
        cap_value = total_value * self.MAX_POSITION_PCT
        room = cap_value - existing_qty * price
        allowed = max(0, math.floor(room / price)) if room > 0 else 0
        label = pct_label(self.MAX_POSITION_PCT)
        if allowed <= 0:
            return 0, (
                f"Position cap: {ticker} already at or above {label} of portfolio "
                f"(cap Rs {cap_value:,.0f}, held {existing_qty} shares); buy skipped."
            )
        if allowed < quantity:
            return allowed, (
                f"Position cap: buy of {quantity} {ticker} reduced to {allowed} "
                f"to stay within {label} of portfolio (held {existing_qty})."
            )
        return quantity, ""
