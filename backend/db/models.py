# db/models.py
from decimal import Decimal

from sqlalchemy import Column, Integer, String, Float, Numeric, DateTime, ForeignKey, Boolean, Text, CheckConstraint, Index
from sqlalchemy.orm import relationship
from database import Base, db_utcnow

# Money columns use Numeric(14, 2) — exact decimal (paise-precision, up to
# ₹999,999,999,999.99), not Float. A trading platform accumulating balances
# over many trades cannot use binary float for stored money: individually
# tiny rounding errors compound across trades and can eventually trip the
# cash_balance >= 0 CheckConstraint on a balance that's actually zero.
# Ratios/percentages/scores (position_size_pct, TraderScore.*) stay Float —
# they're derived display values, not accumulated ledger amounts.


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=db_utcnow)
    is_ai = Column(Boolean, default=False)

    portfolios = relationship("Portfolio", back_populates="user")
    trader_scores = relationship("TraderScore", back_populates="user")


class Season(Base):
    __tablename__ = "seasons"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False)  # e.g. "Season 3"
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    starting_capital = Column(Float, default=100000.0)
    is_active = Column(Boolean, default=True)

    # Partial unique index: at most one row with is_active=True at a time.
    # Closes the race where two workers booting simultaneously both see no
    # active season and both create one — the second INSERT now fails with
    # an IntegrityError instead of silently producing two active seasons.
    __table_args__ = (
        Index(
            "uq_seasons_one_active",
            "is_active",
            unique=True,
            sqlite_where=is_active.is_(True),
            postgresql_where=is_active.is_(True),
        ),
    )

    portfolios = relationship("Portfolio", back_populates="season")


class Portfolio(Base):
    __tablename__ = "portfolios"
    __table_args__ = (
        CheckConstraint("cash_balance >= 0", name="chk_portfolio_cash_balance_non_negative"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    season_id = Column(Integer, ForeignKey("seasons.id"), nullable=False)
    cash_balance = Column(Numeric(14, 2), default=Decimal("100000.00"))
    created_at = Column(DateTime, default=db_utcnow)

    user = relationship("User", back_populates="portfolios")
    season = relationship("Season", back_populates="portfolios")
    positions = relationship("Position", back_populates="portfolio")
    trades = relationship("TradeRecord", back_populates="portfolio")


class Position(Base):
    __tablename__ = "positions"
    __table_args__ = (
        CheckConstraint("quantity >= 0", name="chk_position_quantity_non_negative"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    # Postgres doesn't auto-index FK columns; leaderboard/history queries
    # filter on portfolio_id constantly, so this would full-scan at scale
    # without an explicit index.
    portfolio_id = Column(Integer, ForeignKey("portfolios.id"), nullable=False, index=True)
    ticker = Column(String(20), nullable=False)
    quantity = Column(Integer, default=0)
    avg_price = Column(Numeric(14, 2), default=Decimal("0"))
    state = Column(String(20), default="confirmed")  # "pending" or "confirmed"
    settlement_date = Column(String(10), nullable=True)
    created_at = Column(DateTime, default=db_utcnow)
    updated_at = Column(DateTime, default=db_utcnow, onupdate=db_utcnow)

    portfolio = relationship("Portfolio", back_populates="positions")


class TradeRecord(Base):
    __tablename__ = "trades"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="chk_trade_quantity_positive"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    portfolio_id = Column(Integer, ForeignKey("portfolios.id"), nullable=False, index=True)
    order_id = Column(String(36), nullable=False)
    ticker = Column(String(20), nullable=False)
    side = Column(String(10), nullable=False)  # "buy" or "sell"
    order_type = Column(String(10), nullable=False)  # "market" or "limit"
    quantity = Column(Integer, nullable=False)
    price = Column(Numeric(14, 2), nullable=False)
    fees = Column(Numeric(14, 2), default=Decimal("0"))
    settlement_date = Column(String(10), nullable=True)
    stop_loss_set = Column(Boolean, default=False)
    guardrail_triggered = Column(Boolean, default=False)
    position_size_pct = Column(Float, default=0.0)
    source = Column(String(20), default="human")
    created_at = Column(DateTime, default=db_utcnow)

    portfolio = relationship("Portfolio", back_populates="trades")


class TraderScore(Base):
    __tablename__ = "trader_scores"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    season_id = Column(Integer, ForeignKey("seasons.id"), nullable=False)
    returns_score = Column(Float, default=0.0)
    risk_score = Column(Float, default=0.0)
    consistency_score = Column(Float, default=0.0)
    discipline_score = Column(Float, default=0.0)
    final_score = Column(Integer, default=300)
    grade = Column(String(20), default="Beginner")
    calculated_at = Column(DateTime, default=db_utcnow)

    user = relationship("User", back_populates="trader_scores")


class DailyPortfolioValue(Base):
    __tablename__ = "daily_portfolio_values"

    id = Column(Integer, primary_key=True, autoincrement=True)
    portfolio_id = Column(Integer, ForeignKey("portfolios.id"), nullable=False)
    date = Column(String(10), nullable=False)
    total_value = Column(Numeric(14, 2), nullable=False)
    created_at = Column(DateTime, default=db_utcnow)


class AIDecision(Base):
    __tablename__ = "ai_decisions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    action = Column(String(10), nullable=False)  # "buy", "sell", "hold", "blocked"
    ticker = Column(String(20), nullable=True)
    quantity = Column(Integer, nullable=True)
    reasoning = Column(Text, nullable=True)
    confidence = Column(Float, nullable=True)
    stop_loss_price = Column(Float, nullable=True)
    position_size_pct = Column(Float, nullable=True)
    guardrail_status = Column(String(20), default="approved")  # "approved" or "blocked"
    guardrail_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=db_utcnow)


class UserScript(Base):
    __tablename__ = "user_scripts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(100), nullable=False)
    code = Column(Text, nullable=False)
    created_at = Column(DateTime, default=db_utcnow)
    updated_at = Column(DateTime, default=db_utcnow, onupdate=db_utcnow)
