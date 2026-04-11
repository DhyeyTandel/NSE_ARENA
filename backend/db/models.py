# db/models.py
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
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

    portfolios = relationship("Portfolio", back_populates="season")


class Portfolio(Base):
    __tablename__ = "portfolios"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    season_id = Column(Integer, ForeignKey("seasons.id"), nullable=False)
    cash_balance = Column(Float, default=100000.0)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="portfolios")
    season = relationship("Season", back_populates="portfolios")
    positions = relationship("Position", back_populates="portfolio")
    trades = relationship("TradeRecord", back_populates="portfolio")


class Position(Base):
    __tablename__ = "positions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    portfolio_id = Column(Integer, ForeignKey("portfolios.id"), nullable=False)
    ticker = Column(String(20), nullable=False)
    quantity = Column(Integer, default=0)
    avg_price = Column(Float, default=0.0)
    state = Column(String(20), default="confirmed")  # "pending" or "confirmed"
    settlement_date = Column(String(10), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    portfolio = relationship("Portfolio", back_populates="positions")


class TradeRecord(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, autoincrement=True)
    portfolio_id = Column(Integer, ForeignKey("portfolios.id"), nullable=False)
    order_id = Column(String(36), nullable=False)
    ticker = Column(String(20), nullable=False)
    side = Column(String(10), nullable=False)  # "buy" or "sell"
    order_type = Column(String(10), nullable=False)  # "market" or "limit"
    quantity = Column(Integer, nullable=False)
    price = Column(Float, nullable=False)
    fees = Column(Float, default=0.0)
    settlement_date = Column(String(10), nullable=True)
    stop_loss_set = Column(Boolean, default=False)
    guardrail_triggered = Column(Boolean, default=False)
    position_size_pct = Column(Float, default=0.0)
    source = Column(String(20), default="human")
    created_at = Column(DateTime, default=datetime.utcnow)

    portfolio = relationship("Portfolio", back_populates="trades")


class TraderScore(Base):
    __tablename__ = "trader_scores"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    season_id = Column(Integer, nullable=False)
    returns_score = Column(Float, default=0.0)
    risk_score = Column(Float, default=0.0)
    consistency_score = Column(Float, default=0.0)
    discipline_score = Column(Float, default=0.0)
    final_score = Column(Integer, default=300)
    grade = Column(String(20), default="Beginner")
    calculated_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="trader_scores")


class DailyPortfolioValue(Base):
    __tablename__ = "daily_portfolio_values"

    id = Column(Integer, primary_key=True, autoincrement=True)
    portfolio_id = Column(Integer, ForeignKey("portfolios.id"), nullable=False)
    date = Column(String(10), nullable=False)
    total_value = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


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
    created_at = Column(DateTime, default=datetime.utcnow)
