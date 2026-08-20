# engine/fee_engine.py
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from .money import to_decimal


def _round2(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _round4(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


@dataclass
class FeeBreakdown:
    stt: Decimal
    brokerage: Decimal
    exchange_charge: Decimal
    sebi_charge: Decimal
    gst: Decimal
    total: Decimal


class FeeEngine:
    def calculate(self, price, quantity: int,
                  side: str, trade_type: str = "delivery") -> FeeBreakdown:
        price = to_decimal(price)
        value = price * quantity

        if trade_type == "delivery":
            stt = value * Decimal("0.001")  # 0.1% both sides
        else:  # intraday
            stt = value * Decimal("0.00025") if side == "sell" else Decimal("0")

        brokerage = min(value * Decimal("0.0003"), Decimal("20.00"))
        exchange_charge = value * Decimal("0.0000345")
        sebi_charge = value * Decimal("0.000001")
        subtotal = stt + brokerage + exchange_charge + sebi_charge
        gst = subtotal * Decimal("0.18")

        return FeeBreakdown(
            stt=_round2(stt),
            brokerage=_round2(brokerage),
            exchange_charge=_round4(exchange_charge),
            sebi_charge=_round4(sebi_charge),
            gst=_round2(gst),
            total=_round2(subtotal + gst),
        )
