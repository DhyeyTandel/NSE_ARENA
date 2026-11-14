# tests/test_config.py
"""Unit tests for config.py — verify defaults and constants."""

import importlib
import os

import pytest

import config


def test_default_values_exist():
    """All expected config constants should be defined."""
    assert hasattr(config, "DATABASE_URL")
    assert hasattr(config, "REDIS_URL")
    assert hasattr(config, "GROQ_API_KEY")
    assert hasattr(config, "GROQ_MODEL")
    assert hasattr(config, "SECRET_KEY")
    assert hasattr(config, "ALGORITHM")
    assert hasattr(config, "ACCESS_TOKEN_EXPIRE_MINUTES")
    assert hasattr(config, "STARTING_CAPITAL")


def test_starting_capital():
    """Default paper trading capital should be ₹1,00,000."""
    assert config.STARTING_CAPITAL == 100_000.0


def test_algorithm_is_hs256():
    """JWT algorithm should be HS256."""
    assert config.ALGORITHM == "HS256"


def test_cors_origins_defaults_to_local_dev_origins():
    assert config.CORS_ORIGINS == ["http://localhost:5173", "http://localhost:3000"]


def test_cors_origins_env_driven(monkeypatch):
    """P1 audit fix: CORS was hardcoded to localhost in main.py, which
    hard-failed against any real deployed frontend origin. Now env-driven."""
    monkeypatch.setenv("CORS_ORIGINS", "https://app.example.com, https://staging.example.com")
    try:
        importlib.reload(config)
        assert config.CORS_ORIGINS == ["https://app.example.com", "https://staging.example.com"]
    finally:
        monkeypatch.delenv("CORS_ORIGINS", raising=False)
        importlib.reload(config)


def test_production_sqlite_refuses_to_boot(monkeypatch):
    """Item 2: with_for_update() is a no-op on SQLite, so ENV=production
    must refuse to boot against a sqlite DATABASE_URL."""
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///./nse_arena.db")
    try:
        with pytest.raises(RuntimeError, match="sqlite"):
            importlib.reload(config)
    finally:
        monkeypatch.setenv("ENV", "development")
        monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///./nse_arena.db")
        importlib.reload(config)


def _reload_in_production(monkeypatch, secret):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@db/x")
    monkeypatch.setenv("SECRET_KEY", secret)
    importlib.reload(config)


@pytest.fixture
def restore_config(monkeypatch):
    original_key = os.environ["SECRET_KEY"]
    yield
    monkeypatch.setenv("ENV", "development")
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///./nse_arena.db")
    monkeypatch.setenv("SECRET_KEY", original_key)
    importlib.reload(config)


@pytest.mark.parametrize("secret", [
    "short-but-random-9x",                                   # < 32 chars
    "Change-This-To-A-Random-Secret-Key-In-Production",       # example file value, mixed case
    "change-this-" + "x" * 40,
    "YOUR-SECRET-" + "x" * 40,
    "changeme" + "x" * 40,
])
def test_production_rejects_weak_or_placeholder_secret(monkeypatch, restore_config, secret):
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        _reload_in_production(monkeypatch, secret)


def test_production_accepts_strong_secret(monkeypatch, restore_config):
    _reload_in_production(monkeypatch, "a1b2c3d4" * 8)
    assert config.SECRET_KEY == "a1b2c3d4" * 8


def test_development_stays_lenient_about_short_secret(monkeypatch, restore_config):
    monkeypatch.setenv("ENV", "development")
    monkeypatch.setenv("SECRET_KEY", "short")
    importlib.reload(config)
    assert config.SECRET_KEY == "short"
