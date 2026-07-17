# config.py
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./nse_arena.db")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY or SECRET_KEY == "your-secret-key-change-in-production":
    if "PYTEST_CURRENT_TEST" in os.environ:
        SECRET_KEY = "test-secret-key-fallback-that-is-long-enough-to-prevent-any-jwt-signing-error"
    else:
        raise RuntimeError(
            "SECRET_KEY environment variable is required and must be changed in production. "
            "It cannot be missing or set to the default placeholder."
        )

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours
STARTING_CAPITAL = 100000.0  # ₹1,00,000
