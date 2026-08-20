# tests/test_ai_agent_timeout.py
"""FOLLOWUP 'also verify': the AI agent's Gemini call had no timeout —
generate_content_async is awaited (confirmed non-blocking on the event
loop already), but a hung upstream call would still stall that one AI
scheduler cycle indefinitely. Wrap it in asyncio.wait_for.
"""
import asyncio

import pytest

from ai.agent import AIAgent


def _portfolio():
    return {
        "current_value": 100000,
        "starting_capital": 100000,
        "days_remaining": 10,
        "positions": [],
    }


@pytest.mark.asyncio
async def test_run_cycle_returns_hold_on_timeout(monkeypatch):
    import ai.agent as agent_module

    # Patch the module-level constant down to something the test can
    # actually wait for — run_cycle looks it up dynamically at call time.
    monkeypatch.setattr(agent_module, "GEMINI_CALL_TIMEOUT_SECONDS", 0.05)

    agent = AIAgent(_portfolio(), order_engine=None)

    async def hangs_forever(*args, **kwargs):
        await asyncio.sleep(10)

    monkeypatch.setattr(agent.model, "generate_content_async", hangs_forever)

    decision = await agent.run_cycle({"RELIANCE": {"price": 1000}})

    assert decision["action"] == "hold"
    assert "timed out" in decision["reason"]


@pytest.mark.asyncio
async def test_run_cycle_succeeds_when_gemini_responds_promptly(monkeypatch):
    agent = AIAgent(_portfolio(), order_engine=None)

    class FakeResponse:
        text = '{"action": "hold", "reason": "no clear edge"}'

    async def fast_response(*args, **kwargs):
        return FakeResponse()

    monkeypatch.setattr(agent.model, "generate_content_async", fast_response)

    decision = await agent.run_cycle({"RELIANCE": {"price": 1000}})

    assert decision["action"] == "hold"
    assert decision["reason"] == "no clear edge"


def test_to_order_rejects_unrecognized_action():
    """P1 audit fix: _to_order used to default any unrecognized action to
    SELL. It's unreachable via run_cycle now that guardrails.validate()
    rejects non-buy/sell/hold actions first, but _to_order itself must
    still refuse to guess rather than silently defaulting to SELL."""
    agent = AIAgent(_portfolio(), order_engine=None)
    try:
        agent._to_order({"action": "short", "ticker": "RELIANCE", "quantity": 1})
        assert False, "expected ValueError"
    except ValueError as e:
        assert "short" in str(e)
