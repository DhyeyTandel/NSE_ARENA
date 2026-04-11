# tests/test_config.py
"""Unit tests for config.py — verify defaults and constants."""

import config


def test_default_values_exist():
    """All expected config constants should be defined."""
    assert hasattr(config, "DATABASE_URL")
    assert hasattr(config, "REDIS_URL")
    assert hasattr(config, "GEMINI_API_KEY")
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
