# tests/test_trader_score.py
"""Priority E item 3: _discipline_score used to sum penalties across every
trade with a fixed floor of 0, so an active trader with a LOW violation
rate could still score worse than a quiet trader with the SAME rate,
purely from having made more trades. _consistency_score's docstring
claimed streak-weighting but the implementation was flat win-rate.
"""
import pandas as pd

from scoring.trader_score import TraderScoreCalculator


def _trade(stop_loss_set=True, guardrail_triggered=False, position_size_pct=0.1):
    return {
        "stop_loss_set": stop_loss_set,
        "guardrail_triggered": guardrail_triggered,
        "position_size_pct": position_size_pct,
    }


class TestDisciplineScore:
    def test_no_trades_is_neutral(self):
        calc = TraderScoreCalculator()
        assert calc._discipline_score([]) == 80.0

    def test_perfect_discipline_scores_100(self):
        calc = TraderScoreCalculator()
        trades = [_trade() for _ in range(20)]
        assert calc._discipline_score(trades) == 100.0

    def test_same_violation_rate_scores_equally_regardless_of_volume(self):
        """A quiet trader (5 trades, 1 violation = 20% rate) and an active
        trader (50 trades, 10 violations = same 20% rate) must score the
        same discipline — frequency alone must not be a penalty."""
        calc = TraderScoreCalculator()
        quiet = [_trade(stop_loss_set=False)] + [_trade() for _ in range(4)]
        active = [_trade(stop_loss_set=False) for _ in range(10)] + [_trade() for _ in range(40)]

        assert calc._discipline_score(quiet) == calc._discipline_score(active)

    def test_higher_violation_rate_scores_worse(self):
        calc = TraderScoreCalculator()
        low_rate = [_trade(stop_loss_set=False)] + [_trade() for _ in range(9)]
        high_rate = [_trade(stop_loss_set=False) for _ in range(5)] + [_trade() for _ in range(5)]

        assert calc._discipline_score(high_rate) < calc._discipline_score(low_rate)


class TestConsistencyScore:
    def test_no_returns_is_neutral(self):
        calc = TraderScoreCalculator()
        assert calc._consistency_score(pd.Series(dtype=float)) == 50.0

    def test_sustained_streak_beats_choppy_alternation_at_equal_win_rate(self):
        """Same win rate (5/10 positive days) achieved two ways: one
        sustained 5-day run of gains, one alternating win/loss/win/loss.
        The sustained run must score higher — that's the whole point of
        streak-weighting the docstring already claimed."""
        calc = TraderScoreCalculator()
        sustained = pd.Series([0.01, 0.01, 0.01, 0.01, 0.01, -0.01, -0.01, -0.01, -0.01, -0.01])
        choppy = pd.Series([0.01, -0.01, 0.01, -0.01, 0.01, -0.01, 0.01, -0.01, 0.01, -0.01])

        assert calc._consistency_score(sustained) > calc._consistency_score(choppy)

    def test_bigger_wins_than_losses_scores_higher_at_equal_win_rate(self):
        """Same win rate and same streak shape, but one trader's wins are
        much bigger than their losses — magnitude symmetry should reward
        that over a trader whose wins and losses are the same size."""
        calc = TraderScoreCalculator()
        big_wins = pd.Series([0.05, -0.01, 0.05, -0.01])
        even = pd.Series([0.01, -0.01, 0.01, -0.01])

        assert calc._consistency_score(big_wins) > calc._consistency_score(even)

    def test_all_positive_days_scores_100(self):
        calc = TraderScoreCalculator()
        all_wins = pd.Series([0.01, 0.02, 0.01, 0.015])
        assert calc._consistency_score(all_wins) == 100.0
