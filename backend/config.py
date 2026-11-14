# config.py
import os
from dotenv import load_dotenv

load_dotenv()

ENV = os.getenv("ENV", "development")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./nse_arena.db")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

# Optional Zerodha Kite Connect real-time feed (read-only market data; the
# app never places orders). Both empty = feature off and the app behaves
# exactly as before, polling Yahoo only.
KITE_API_KEY = os.getenv("KITE_API_KEY", "").strip()
KITE_API_SECRET = os.getenv("KITE_API_SECRET", "").strip()

# Comma-separated usernames allowed to connect/disconnect the shared Kite
# session. Stored lower-cased; compare case-insensitively. Empty = nobody.
ADMIN_USERNAMES = {
    name.strip().lower()
    for name in os.getenv("ADMIN_USERNAMES", "").split(",")
    if name.strip()
}

# Where the Kite callback sends the browser afterwards. Empty = same-origin
# "/" (the SPA behind the production reverse proxy); local dev sets e.g.
# http://localhost:5173. Trailing slash stripped. Never taken from a request.
FRONTEND_URL = os.getenv("FRONTEND_URL", "").strip().rstrip("/")

# How often live prices are polled from yfinance while NSE is open. Floored
# at 5s: Yahoo rate-limits aggressive polling and its quotes are delayed
# anyway, so going lower buys nothing.
PRICE_POLL_INTERVAL_SECONDS = max(5, int(os.getenv("PRICE_POLL_INTERVAL_SECONDS", "15")))

# Comma-separated list of allowed frontend origins for CORS. Defaults to
# the local Vite/CRA dev origins so nothing breaks out of the box; a real
# deployment sets CORS_ORIGINS to its actual frontend origin(s) — main.py
# previously hardcoded just the two localhost origins, which hard-failed
# CORS against any deployed frontend unless hand-edited.
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")
    if origin.strip()
]

if ENV == "production" and DATABASE_URL.startswith("sqlite"):
    raise RuntimeError(
        "DATABASE_URL is sqlite but ENV=production. Row-locking guarantees "
        "(with_for_update) are a silent no-op on SQLite, so production must "
        "run on Postgres. Refusing to boot."
    )

# Placeholder values shipped in docs / .env.example. Matched
# case-insensitively as prefixes when ENV=production.
SECRET_KEY_PLACEHOLDER_PREFIXES = ("change-this", "your-secret", "changeme")
# Exact value in backend/.env.example (also covered by the prefixes above).
SECRET_KEY_EXAMPLE_VALUE = "change-this-to-a-random-secret-key-in-production"
SECRET_KEY_MIN_LENGTH = 32


def validate_production_secret_key(key: str) -> None:
    """Raise RuntimeError if `key` is too short or looks like a placeholder.
    Only enforced when ENV=production; development stays lenient."""
    lowered = key.strip().lower()
    if len(key) < SECRET_KEY_MIN_LENGTH:
        raise RuntimeError(
            f"SECRET_KEY must be at least {SECRET_KEY_MIN_LENGTH} characters in production."
        )
    if lowered.startswith(SECRET_KEY_PLACEHOLDER_PREFIXES) or lowered == SECRET_KEY_EXAMPLE_VALUE:
        raise RuntimeError(
            "SECRET_KEY looks like a placeholder value. Generate a random one "
            "(e.g. `openssl rand -hex 32`) before running in production."
        )


SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY or SECRET_KEY == "your-secret-key-change-in-production":
    if "PYTEST_CURRENT_TEST" in os.environ:
        SECRET_KEY = "test-secret-key-fallback-that-is-long-enough-to-prevent-any-jwt-signing-error"
    else:
        raise RuntimeError(
            "SECRET_KEY environment variable is required and must be changed in production. "
            "It cannot be missing or set to the default placeholder."
        )

if ENV == "production":
    validate_production_secret_key(SECRET_KEY)

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours
STARTING_CAPITAL = 100000.0  # ₹1,00,000
