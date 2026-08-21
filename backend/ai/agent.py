# ai/agent.py
import asyncio
import json
from google import genai
from google.genai import types as genai_types
from .risk_memory import AIRiskMemory
from .guardrails import RiskGuardrail
from .prompts import SYSTEM_PROMPT, RESPONSE_FORMAT
from config import GEMINI_API_KEY
from services.trading import TradeRejected

GEMINI_CALL_TIMEOUT_SECONDS = 30
GEMINI_MODEL_NAME = "gemini-1.5-pro"


class AIAgent:
    def __init__(self, portfolio, order_engine, risk_memory: AIRiskMemory | None = None):
        self.portfolio = portfolio
        self.order_engine = order_engine
        self.memory = risk_memory if risk_memory is not None else AIRiskMemory()
        self.guardrail = RiskGuardrail()
        # google.genai.Client validates eagerly and raises on an empty key,
        # unlike the old google.generativeai SDK's lenient configure() — a
        # placeholder keeps construction (and tests that monkeypatch
        # self.client.aio.models afterward) working without a real key in
        # dev/test; a real call still fails cleanly against Google's API if
        # GEMINI_API_KEY was genuinely never set in production.
        self.client = genai.Client(api_key=GEMINI_API_KEY or "unset-gemini-api-key")

    async def run_cycle(self, market_data: dict):
        """Called every 30 minutes during market hours"""
        prompt = self._build_prompt(market_data)

        try:
            response = await asyncio.wait_for(
                self.client.aio.models.generate_content(
                    model=GEMINI_MODEL_NAME,
                    contents=prompt,
                    config=genai_types.GenerateContentConfig(
                        temperature=0.3,  # lower = more consistent, less creative
                        response_mime_type="application/json",
                    ),
                ),
                timeout=GEMINI_CALL_TIMEOUT_SECONDS,
            )
            decision = json.loads(response.text)
        except asyncio.TimeoutError:
            return {
                "action": "hold",
                "reason": f"Gemini call timed out after {GEMINI_CALL_TIMEOUT_SECONDS}s",
            }
        except Exception as e:
            return {"action": "hold", "reason": f"Parse error: {e}"}

        # Guardrail check — AI cannot bypass this
        result = self.guardrail.validate(decision, self.portfolio, market_data)
        if not result.approved:
            self.memory.record_violation(decision, result.reason)
            return {"action": "blocked", "reason": result.reason}

        if decision["action"] != "hold":
            try:
                await self.order_engine.submit(self._to_order(decision), market_data)
            except TradeRejected as e:
                # Guardrails approved this decision, but execution still
                # failed (e.g. insufficient balance/shares, market closed,
                # circuit breaker). Log it the same way a guardrail block
                # is logged rather than raising — a single bad cycle must
                # not take down the whole scheduler run.
                self.memory.record_violation(decision, str(e))
                return {"action": "blocked", "reason": str(e)}

        self.memory.record_decision(decision)
        return decision

    def _build_prompt(self, market_data: dict) -> str:
        pv = self.portfolio.get("current_value", 100000)
        start = self.portfolio.get("starting_capital", 100000)
        drawdown = (pv - start) / start if start > 0 else 0
        recovery_needed = (1 / (1 + drawdown)) - 1 if drawdown < 0 else 0

        return f"""
{SYSTEM_PROMPT}

=== YOUR CURRENT STATE ===
Starting capital:   ₹{start:,.0f}
Current value:      ₹{pv:,.0f}
Total return:       {(pv/start - 1):+.1%}
Current drawdown:   {drawdown:.1%}
Recovery to break even: {recovery_needed:+.1%}
Days left in season: {self.portfolio.get('days_remaining', 0)}

=== HARD LIMITS (your engine will reject violations) ===
Max single position: 20% of capital = ₹{pv * 0.20:,.0f}
Stop loss: MANDATORY on every trade
Kill switch: trading halted if drawdown exceeds -15%

=== YOUR RECENT HISTORY ===
{self.memory.format_for_prompt()}

=== OPEN POSITIONS ===
{self._format_positions()}

=== MARKET DATA ===
{json.dumps(market_data, indent=2)}

{RESPONSE_FORMAT}
"""

    def _format_positions(self) -> str:
        positions = self.portfolio.get("positions", [])
        if not positions:
            return "No open positions."
        lines = []
        for p in positions:
            lines.append(
                f"  {p['ticker']}: {p['quantity']} shares @ ₹{p['avg_price']:,.2f}"
            )
        return "\n".join(lines)

    def _to_order(self, decision: dict):
        from engine.models import Order, OrderSide, OrderType

        action = decision["action"]
        if action == "buy":
            side = OrderSide.BUY
        elif action == "sell":
            side = OrderSide.SELL
        else:
            # The guardrail already rejects any action outside
            # {buy, sell, hold} before run_cycle ever calls _to_order, and
            # "hold" never reaches this method either (run_cycle only
            # calls it when action != "hold") — this is a defense-in-depth
            # backstop, not a reachable path today. Explicitly refusing to
            # guess is the point: silently defaulting an unrecognized
            # action to SELL is exactly the bug this replaces.
            raise ValueError(f"_to_order called with non-tradeable action: {action!r}")

        return Order(
            user_id="ai_agent",
            ticker=decision.get("ticker", ""),
            side=side,
            order_type=OrderType.LIMIT if decision.get("order_type") == "limit" else OrderType.MARKET,
            quantity=decision.get("quantity", 0),
            limit_price=decision.get("limit_price", 0.0) or 0.0,
            source="ai_agent",
        )
