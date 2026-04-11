# engine/models.py
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import uuid


class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"


class OrderStatus(Enum):
    PENDING = "pending"
    PARTIAL = "partial"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


@dataclass
class Order:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    ticker: str = ""
    side: OrderSide = OrderSide.BUY
    order_type: OrderType = OrderType.MARKET
    quantity: int = 0
    limit_price: float = 0.0
    filled_quantity: int = 0
    avg_fill_price: float = 0.0
    status: OrderStatus = OrderStatus.PENDING
    timestamp: datetime = field(default_factory=datetime.utcnow)
    source: str = "human"  # "human" or "ai_agent"


@dataclass
class Trade:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    buy_order_id: str = ""
    sell_order_id: str = ""
    ticker: str = ""
    price: float = 0.0
    quantity: int = 0
    fees: float = 0.0
    settlement_date: str = ""  # T+1 date as YYYY-MM-DD
    timestamp: datetime = field(default_factory=datetime.utcnow)
