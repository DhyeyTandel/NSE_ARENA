# ai/risk_memory.py
from datetime import datetime
from collections import deque


class AIRiskMemory:
    """Logs the AI's past decisions and outcomes, formats history for prompt injection."""

    def __init__(self, max_entries: int = 50):
        self.decisions: deque = deque(maxlen=max_entries)
        self.violations: deque = deque(maxlen=20)

    def record_decision(self, decision: dict) -> None:
        """Log a decision made by the AI"""
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "action": decision.get("action", "hold"),
            "ticker": decision.get("ticker", ""),
            "quantity": decision.get("quantity", 0),
            "reasoning": decision.get("reasoning", ""),
            "confidence": decision.get("confidence", 0.0),
        }
        self.decisions.append(entry)

    def record_violation(self, decision: dict, reason: str) -> None:
        """Log a guardrail violation"""
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "attempted_action": decision.get("action", ""),
            "ticker": decision.get("ticker", ""),
            "blocked_reason": reason,
        }
        self.violations.append(entry)

    def format_for_prompt(self) -> str:
        """Format recent history for injection into the AI prompt"""
        if not self.decisions and not self.violations:
            return "No previous decisions recorded."

        lines = []

        # Last 5 decisions
        recent = list(self.decisions)[-5:]
        if recent:
            lines.append("Last 5 decisions:")
            for d in recent:
                lines.append(
                    f"  [{d['timestamp'][:16]}] {d['action'].upper()} {d['ticker']} "
                    f"x{d['quantity']} (confidence: {d['confidence']:.0%}) — {d['reasoning']}"
                )

        # Recent violations
        recent_violations = list(self.violations)[-3:]
        if recent_violations:
            lines.append("\nRecent guardrail violations:")
            for v in recent_violations:
                lines.append(
                    f"  [{v['timestamp'][:16]}] BLOCKED: {v['attempted_action']} {v['ticker']} — {v['blocked_reason']}"
                )

        return "\n".join(lines)
