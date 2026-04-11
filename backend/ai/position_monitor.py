# ai/position_monitor.py
import asyncio
from datetime import datetime


class PositionMonitor:
    """
    Auto-triggers stop losses independently of the AI.
    Runs as a background task during market hours.
    """

    def __init__(self, order_engine):
        self.order_engine = order_engine
        self.stop_losses: dict = {}  # {ticker: {"price": float, "quantity": int, "user_id": str}}
        self.running = False

    def set_stop_loss(self, ticker: str, user_id: str,
                      stop_price: float, quantity: int) -> None:
        """Register a stop loss for a position"""
        key = f"{user_id}:{ticker}"
        self.stop_losses[key] = {
            "ticker": ticker,
            "user_id": user_id,
            "price": stop_price,
            "quantity": quantity,
            "set_at": datetime.utcnow().isoformat(),
        }

    def remove_stop_loss(self, ticker: str, user_id: str) -> None:
        """Remove a stop loss when position is closed"""
        key = f"{user_id}:{ticker}"
        self.stop_losses.pop(key, None)

    async def check_prices(self, current_prices: dict) -> list[dict]:
        """
        Check current prices against all stop losses.
        Returns list of triggered stop losses.
        """
        triggered = []
        keys_to_remove = []

        for key, stop in self.stop_losses.items():
            ticker = stop["ticker"]
            if ticker in current_prices:
                current_price = current_prices[ticker]
                if current_price <= stop["price"]:
                    triggered.append({
                        "ticker": ticker,
                        "user_id": stop["user_id"],
                        "stop_price": stop["price"],
                        "trigger_price": current_price,
                        "quantity": stop["quantity"],
                        "triggered_at": datetime.utcnow().isoformat(),
                    })
                    keys_to_remove.append(key)

        # Remove triggered stop losses
        for key in keys_to_remove:
            del self.stop_losses[key]

        return triggered

    async def run_monitor_loop(self, price_fetcher, interval: int = 60):
        """
        Background loop that checks stop losses periodically.
        Should run every 60 seconds during market hours.
        """
        self.running = True
        while self.running:
            try:
                prices = await price_fetcher()
                triggered = await self.check_prices(prices)
                for stop in triggered:
                    # Execute market sell order for triggered stop loss
                    from engine.models import Order, OrderSide, OrderType
                    sell_order = Order(
                        user_id=stop["user_id"],
                        ticker=stop["ticker"],
                        side=OrderSide.SELL,
                        order_type=OrderType.MARKET,
                        quantity=stop["quantity"],
                        source="ai_agent",
                    )
                    await self.order_engine.submit(sell_order)
            except Exception:
                pass
            await asyncio.sleep(interval)

    def stop(self):
        self.running = False
