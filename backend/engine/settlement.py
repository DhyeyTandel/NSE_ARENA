# engine/settlement.py
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import pytz

IST = pytz.timezone("Asia/Kolkata")


class PositionState(Enum):
    PENDING = "pending"      # T+0: just bought, not yet settled
    CONFIRMED = "confirmed"  # T+1: settled, can be sold


@dataclass
class Position:
    ticker: str = ""
    quantity: int = 0
    avg_price: float = 0.0
    state: PositionState = PositionState.PENDING
    trade_date: datetime = field(default_factory=datetime.utcnow)
    settlement_date: str = ""  # YYYY-MM-DD when it becomes confirmed


class SettlementEngine:
    """
    T+1 settlement: bought shares are 'pending' for one trading day
    before appearing as confirmed holdings.
    Settlement runs at 6 PM IST.
    """

    def calculate_settlement_date(self, trade_date: datetime) -> str:
        """Calculate T+1 settlement date (next trading day at 6 PM IST)"""
        ist_date = trade_date.astimezone(IST) if trade_date.tzinfo else IST.localize(trade_date)
        next_day = ist_date + timedelta(days=1)

        # Skip weekends
        while next_day.weekday() >= 5:  # Saturday=5, Sunday=6
            next_day += timedelta(days=1)

        return next_day.strftime("%Y-%m-%d")

    def create_pending_position(self, ticker: str, quantity: int,
                                 price: float, trade_date: datetime) -> Position:
        """Create a new pending position from a buy trade"""
        settlement_date = self.calculate_settlement_date(trade_date)
        return Position(
            ticker=ticker,
            quantity=quantity,
            avg_price=price,
            state=PositionState.PENDING,
            trade_date=trade_date,
            settlement_date=settlement_date,
        )

    def settle_positions(self, positions: list[Position]) -> list[Position]:
        """
        Called at 6 PM IST daily.
        Convert pending positions to confirmed if settlement date <= today.
        """
        now = datetime.now(IST)
        today = now.strftime("%Y-%m-%d")
        current_time = now.time()

        settled = []
        for pos in positions:
            if pos.state == PositionState.PENDING:
                if pos.settlement_date <= today and current_time.hour >= 18:
                    pos.state = PositionState.CONFIRMED
                    settled.append(pos)
        return settled

    def get_available_quantity(self, positions: list[Position], ticker: str) -> int:
        """Only confirmed positions can be sold"""
        return sum(
            p.quantity for p in positions
            if p.ticker == ticker and p.state == PositionState.CONFIRMED
        )

    def get_total_quantity(self, positions: list[Position], ticker: str) -> int:
        """Total quantity including pending"""
        return sum(
            p.quantity for p in positions
            if p.ticker == ticker
        )
