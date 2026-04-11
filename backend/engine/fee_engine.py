# engine/fee_engine.py
from dataclasses import dataclass


@dataclass
class FeeBreakdown:
    stt: float
    brokerage: float
    exchange_charge: float
    sebi_charge: float
    gst: float
    total: float


class FeeEngine:
    def calculate(self, price: float, quantity: int,
                  side: str, trade_type: str = "delivery") -> FeeBreakdown:
        value = price * quantity

        if trade_type == "delivery":
            stt = value * 0.001  # 0.1% both sides
        else:  # intraday
            stt = value * 0.00025 if side == "sell" else 0.0

        brokerage = min(value * 0.0003, 20.0)
        exchange_charge = value * 0.0000345
        sebi_charge = value * 0.000001
        subtotal = stt + brokerage + exchange_charge + sebi_charge
        gst = subtotal * 0.18

        return FeeBreakdown(
            stt=round(stt, 2),
            brokerage=round(brokerage, 2),
            exchange_charge=round(exchange_charge, 4),
            sebi_charge=round(sebi_charge, 4),
            gst=round(gst, 2),
            total=round(subtotal + gst, 2)
        )
