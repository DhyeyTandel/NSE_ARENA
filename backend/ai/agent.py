# ai/agent.py
import google.generativeai as genai
import json
from .risk_memory import AIRiskMemory
from .guardrails import RiskGuardrail
from .prompts import SYSTEM_PROMPT, RESPONSE_FORMAT
from config import GEMINI_API_KEY

genai.configure(api_key=GEMINI_API_KEY)


class AIAgent:
    def __init__(self, portfolio, order_engine):
        self.portfolio = portfolio
        self.order_engine = order_engine
        self.memory = AIRiskMemory()
        self.guardrail = RiskGuardrail()
        self.model = genai.GenerativeModel("gemini-1.5-pro")

    async def run_cycle(self, market_data: dict):
        """Called every 30 minutes during market hours"""
        prompt = self._build_prompt(market_data)

        try:
            response = self.model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.3,  # lower = more consistent, less creative
                    response_mime_type="application/json"
                )
            )
            decision = json.loads(response.text)
        except Exception as e:
            return {"action": "hold", "reason": f"Parse error: {e}"}

        # Guardrail check — AI cannot bypass this
        result = self.guardrail.validate(decision, self.portfolio)
        if not result.approved:
            self.memory.record_violation(decision, result.reason)
            return {"action": "blocked", "reason": result.reason}

        if decision["action"] != "hold":
            await self.order_engine.submit(self._to_order(decision))

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
        return Order(
            user_id="ai_agent",
            ticker=decision.get("ticker", ""),
            side=OrderSide.BUY if decision["action"] == "buy" else OrderSide.SELL,
            order_type=OrderType.LIMIT if decision.get("order_type") == "limit" else OrderType.MARKET,
            quantity=decision.get("quantity", 0),
            limit_price=decision.get("limit_price", 0.0) or 0.0,
            source="ai_agent",
        )
