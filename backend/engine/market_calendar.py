# engine/market_calendar.py
"""NSE trading calendar: weekends, market hours, and the 2026 holiday list.

Holiday dates verified 2026-07-17 against the published NSE equity-segment
(Capital Market) holiday calendar for 2026 (nseindia.com "Market Timings &
Holidays", cross-checked with broker calendars). Includes the special
2026-01-15 closure for the Maharashtra municipal elections, declared by
NSE circular on 2026-01-12. Holidays that fall on weekends (e.g.
Independence Day 2026-08-15) are omitted — the weekend rule already
covers them. The Muhurat session (2026-11-08, a Sunday) is not supported.

For years without a holiday list here, only the weekend and market-hours
rules apply.
"""
from datetime import date, datetime, time

import pytz

IST = pytz.timezone("Asia/Kolkata")
MARKET_OPEN = time(9, 15)
MARKET_CLOSE = time(15, 30)

NSE_HOLIDAYS = {
    date(2026, 1, 15): "Maharashtra Municipal Corporation Elections",
    date(2026, 1, 26): "Republic Day",
    date(2026, 3, 3): "Holi",
    date(2026, 3, 26): "Shri Ram Navami",
    date(2026, 3, 31): "Shri Mahavir Jayanti",
    date(2026, 4, 3): "Good Friday",
    date(2026, 4, 14): "Dr. Baba Saheb Ambedkar Jayanti",
    date(2026, 5, 1): "Maharashtra Day",
    date(2026, 5, 28): "Bakri Id",
    date(2026, 6, 26): "Muharram",
    date(2026, 9, 14): "Ganesh Chaturthi",
    date(2026, 10, 2): "Mahatma Gandhi Jayanti",
    date(2026, 10, 20): "Dussehra",
    date(2026, 11, 10): "Diwali - Balipratipada",
    date(2026, 11, 24): "Prakash Gurpurb Sri Guru Nanak Dev",
    date(2026, 12, 25): "Christmas",
}


def holiday_name(d: date) -> str | None:
    return NSE_HOLIDAYS.get(d)


def is_trading_day(d: date) -> bool:
    """Weekday and not an NSE holiday."""
    return d.weekday() < 5 and d not in NSE_HOLIDAYS


def is_market_open(dt: datetime) -> bool:
    """True if `dt` falls within NSE market hours on a trading day.
    Aware datetimes are converted to IST; naive ones are assumed IST."""
    if dt.tzinfo is not None:
        dt = dt.astimezone(IST)
    return is_trading_day(dt.date()) and MARKET_OPEN <= dt.time() <= MARKET_CLOSE
