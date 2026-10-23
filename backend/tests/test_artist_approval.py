import asyncio

import pytest
from fastapi import HTTPException

import server


def _call(payload):
    return asyncio.run(server.require_artist(payload))


def test_default_requires_artist_role(monkeypatch):
    monkeypatch.delenv("ARTIST_APPROVAL_REQUIRED", raising=False)
    with pytest.raises(HTTPException) as e:
        _call({"sub": "u1", "metadata": {}})
    assert e.value.status_code == 403
    assert _call({"sub": "u1", "metadata": {"role": "artist"}})["sub"] == "u1"
    assert _call({"sub": "u1", "metadata": {"role": "admin"}})["sub"] == "u1"


def test_approval_off_lets_unroled_user_through(monkeypatch):
    monkeypatch.setenv("ARTIST_APPROVAL_REQUIRED", "false")
    assert _call({"sub": "u2", "metadata": {}})["sub"] == "u2"
    assert _call({"sub": "u2"})["sub"] == "u2"


def test_approval_off_still_refuses_other_roles(monkeypatch):
    monkeypatch.setenv("ARTIST_APPROVAL_REQUIRED", "false")
    with pytest.raises(HTTPException):
        _call({"sub": "u3", "metadata": {"role": "suspended"}})


def test_admin_routes_unaffected(monkeypatch):
    monkeypatch.setenv("ARTIST_APPROVAL_REQUIRED", "false")
    with pytest.raises(HTTPException):
        asyncio.run(server.require_admin({"sub": "u4", "metadata": {}}))
