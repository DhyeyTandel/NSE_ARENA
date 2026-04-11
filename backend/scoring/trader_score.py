# scoring/trader_score.py
import pandas as pd
import numpy as np
from dataclasses import dataclass

RISK_FREE_RATE_DAILY = 0.065 / 252  # 6.5% annualised / 252 trading days


@dataclass
class TraderScoreBreakdown:
    returns_score: float       # 0-100, weight 30%
    risk_score: float          # 0-100, weight 30%
    consistency_score: float   # 0-100, weight 25%
    discipline_score: float    # 0-100, weight 15%
    final_score: int           # 300-900 (CIBIL-like scale)
    grade: str                 # "Elite" / "Pro" / "Intermediate" / "Beginner"


class TraderScoreCalculator:

    def calculate(self, user_id: str, trades: list,
                  daily_values: list[float]) -> TraderScoreBreakdown:
        if len(daily_values) < 5:
            return self._default_score()

        pv = pd.Series(daily_values)
        daily_returns = pv.pct_change().dropna()

        returns_score = self._returns_score(daily_returns)
        risk_score = self._risk_score(pv, daily_returns)
        consistency_score = self._consistency_score(daily_returns)
        discipline_score = self._discipline_score(trades)

        # Weighted composite
        composite = (
            returns_score * 0.30 +
            risk_score * 0.30 +
            consistency_score * 0.25 +
            discipline_score * 0.15
        )

        # Map 0-100 composite to 300-900 scale
        final_score = int(300 + (composite / 100) * 600)
        final_score = max(300, min(900, final_score))

        grade = self._grade(final_score)

        return TraderScoreBreakdown(
            returns_score=round(returns_score, 1),
            risk_score=round(risk_score, 1),
            consistency_score=round(consistency_score, 1),
            discipline_score=round(discipline_score, 1),
            final_score=final_score,
            grade=grade
        )

    def _returns_score(self, daily_returns: pd.Series) -> float:
        """Sharpe ratio mapped to 0-100"""
        if daily_returns.std() == 0:
            return 50.0
        sharpe = (daily_returns.mean() - RISK_FREE_RATE_DAILY) / daily_returns.std()
        sharpe_annualised = sharpe * np.sqrt(252)
        # Sharpe of 2.0 = perfect score. Below 0 = 0. Clipped.
        return float(np.clip((sharpe_annualised / 2.0) * 100, 0, 100))

    def _risk_score(self, portfolio_values: pd.Series,
                    daily_returns: pd.Series) -> float:
        """Lower max drawdown + lower volatility = higher score"""
        peak = portfolio_values.expanding().max()
        drawdown = (portfolio_values - peak) / peak
        max_drawdown = abs(drawdown.min())

        # Max drawdown score: 0% drawdown = 100, 50%+ drawdown = 0
        drawdown_score = max(0, 100 - (max_drawdown * 200))

        # Volatility score: low vol is better for this metric
        vol_annualised = daily_returns.std() * np.sqrt(252)
        vol_score = max(0, 100 - (vol_annualised * 200))

        return (drawdown_score * 0.6 + vol_score * 0.4)

    def _consistency_score(self, daily_returns: pd.Series) -> float:
        """Percentage of days with positive returns, weighted by streak"""
        if len(daily_returns) == 0:
            return 50.0
        positive_days = (daily_returns > 0).sum()
        win_rate = positive_days / len(daily_returns)
        return float(win_rate * 100)

    def _discipline_score(self, trades: list) -> float:
        """Penalise missing stop losses, overtrading, large single bets"""
        if not trades:
            return 80.0  # neutral if no trades yet

        penalties = 0
        for trade in trades:
            if not trade.get("stop_loss_set"):
                penalties += 10
            if trade.get("guardrail_triggered"):
                penalties += 15
            if trade.get("position_size_pct", 0) > 0.25:
                penalties += 5

        base = 100
        score = max(0, base - penalties)
        return float(score)

    def _grade(self, score: int) -> str:
        if score >= 800: return "Elite"
        if score >= 700: return "Pro"
        if score >= 550: return "Intermediate"
        return "Beginner"

    def _default_score(self) -> TraderScoreBreakdown:
        return TraderScoreBreakdown(
            returns_score=0, risk_score=0, consistency_score=0,
            discipline_score=0, final_score=300, grade="Beginner"
        )
