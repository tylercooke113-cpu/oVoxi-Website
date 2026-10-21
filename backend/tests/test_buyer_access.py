"""Brief 23 Part C: POST /api/account/buyer-access sets public_metadata.buyer via Clerk.
It merges (so an existing role is preserved), is idempotent, and refuses signed-out callers.
conftest mocks motor; the Clerk PATCH is faked so no network call is made."""
import pytest
from fastapi.testclient import TestClient

import server

_CAPTURED = {}


class _FakeResp:
    status_code = 200

    def json(self):
        return {}


class _FakeClient:
    def __init__(self, *a, **k):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def patch(self, url, headers=None, json=None):
        _CAPTURED["url"] = url
        _CAPTURED["json"] = json
        return _FakeResp()


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(server.limiter, "enabled", False)
    monkeypatch.setattr(server, "CLERK_SECRET_KEY", "sk_test")
    monkeypatch.setattr(server.httpx, "AsyncClient", _FakeClient)
    _CAPTURED.clear()
    c = TestClient(server.app)
    yield c
    server.app.dependency_overrides.clear()


def _auth(role="artist"):
    server.app.dependency_overrides[server.verify_clerk_token] = lambda: {
        "sub": "user_1", "metadata": {"role": role},
    }


def test_sets_buyer_true_and_merges(client):
    _auth()
    r = client.post("/api/account/buyer-access")
    assert r.status_code == 200
    assert r.json() == {"buyer": True}
    # Only the buyer key is sent, so Clerk merges it and the existing role is preserved.
    assert _CAPTURED["json"] == {"public_metadata": {"buyer": True}}
    assert "role" not in _CAPTURED["json"]["public_metadata"]
    assert _CAPTURED["url"].endswith("/users/user_1/metadata")


def test_idempotent_second_call(client):
    _auth()
    assert client.post("/api/account/buyer-access").status_code == 200
    assert client.post("/api/account/buyer-access").status_code == 200


def test_signed_out_refused(client):
    r = client.post("/api/account/buyer-access")
    assert r.status_code == 401
