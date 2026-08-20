# engine/money.py
"""Shared helper for the Decimal money path (engine/fee_engine.py,
engine/validator.py, services/trading.py)."""
from decimal import Decimal


def to_decimal(value) -> Decimal:
    """Coerce a float/int/str/Decimal into a Decimal via its string form —
    never construct a Decimal directly from a float, which would bake in
    the float's own binary-representation error (Decimal(0.1) != 0.1)."""
    return value if isinstance(value, Decimal) else Decimal(str(value))
