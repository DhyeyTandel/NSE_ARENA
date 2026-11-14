# tests/test_admin.py
"""Env-based admin role: is_admin / require_admin, Kite gating, /auth/me."""
import asyncio
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

import config
from api.dependencies import get_current_user, is_admin, require_admin
from main import app


def u(name, is_ai=False):
    return SimpleNamespace(id=1, username=name, email="x@y.z", is_ai=is_ai)


@pytest.fixture
def admins():
    with patch.object(config, "ADMIN_USERNAMES", {"boss"}):
        yield


def test_is_admin_rules(admins):
    assert is_admin(u("boss"))
    assert is_admin(u("BOSS"))          # case-insensitive
    assert not is_admin(u("other"))
    assert not is_admin(u("boss", is_ai=True))  # AI never admin
    assert not is_admin(None)


def test_nobody_admin_by_default():
    with patch.object(config, "ADMIN_USERNAMES", set()):
        assert not is_admin(u("boss"))


def test_admin_env_parsing(monkeypatch):
    import importlib
    monkeypatch.setenv("ADMIN_USERNAMES", " Boss , ,Ops")
    try:
        importlib.reload(config)
        assert config.ADMIN_USERNAMES == {"boss", "ops"}
    finally:
        monkeypatch.delenv("ADMIN_USERNAMES")
        importlib.reload(config)


def test_require_admin_ok_and_403(admins):
    assert asyncio.run(require_admin(u("Boss"))).username == "Boss"
    with pytest.raises(HTTPException) as e:
        asyncio.run(require_admin(u("other")))
    assert e.value.status_code == 403 and e.value.detail == "Admin only"
    with pytest.raises(HTTPException):
        asyncio.run(require_admin(u("boss", is_ai=True)))


def test_logged_out_is_401():
    c = TestClient(app, follow_redirects=False)
    assert c.get("/api/kite/login").status_code == 401
    assert c.post("/api/kite/disconnect").status_code == 401


def test_kite_login_disconnect_403_for_non_admin(admins):
    app.dependency_overrides[get_current_user] = lambda: u("other")
    try:
        c = TestClient(app, follow_redirects=False)
        r = c.get("/api/kite/login")
        assert r.status_code == 403 and r.json() == {"detail": "Admin only"}
        assert c.post("/api/kite/disconnect").status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_me_reports_is_admin(admins):
    try:
        c = TestClient(app)
        app.dependency_overrides[get_current_user] = lambda: u("BOSS")
        assert c.get("/auth/me").json()["is_admin"] is True
        app.dependency_overrides[get_current_user] = lambda: u("other")
        assert c.get("/auth/me").json()["is_admin"] is False
    finally:
        app.dependency_overrides.clear()
