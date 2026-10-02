"""PRD-03 Phase 6a: success-page status (with the Stripe fallback) and the download page."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from urllib.parse import parse_qs, unquote, urlparse

import pytest
from fastapi.testclient import TestClient

pytest.importorskip("mongomock")

import server  # noqa: E402
import sync_orders as so  # noqa: E402
from test_checkout import LISTED  # noqa: E402
from test_sync_orders import AsyncDB  # noqa: E402

SID = "cs_test_a1B2c3D4e5F6g7H8"
STEMS = {n: f"catalog/a/b/stems/t1/{n}.wav" for n in so.STEM_NAMES}


class FakeStripeSessions:
    def __init__(self):
        self.calls = 0
        self.payment_status = "paid"
        self.order_id = None

    def retrieve(self, session_id, params=None, options=None):
        self.calls += 1
        data = {"id": session_id, "payment_status": self.payment_status, "payment_intent": "pi_9",
                "metadata": {"order_id": self.order_id}, "amount_subtotal": 2300, "amount_total": 2300,
                "total_details": {"amount_tax": 0}}
        return SimpleNamespace(to_dict=lambda: data)


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("SYNC_TOKEN_SECRET", "s" * 64)
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_abc")
    for name in ("SYNC_DELIVER_STEMS", "SYNC_DOWNLOAD_MAX_PER_FILE", "SYNC_DOWNLOAD_TTL_DAYS"):
        monkeypatch.delenv(name, raising=False)
    db = AsyncDB()
    db._db.track_submissions.insert_one(dict(LISTED, stem_paths=STEMS))
    db._db.sync_profiles.insert_one({"user_id": "user_artist", "sales_count": 0})
    order = so.build_order(track=LISTED, tier="creator", include_stems=True, buyer_name="Dana Secret",
                           buyer_company="Secret Co", buyer_email="dana@secret.example", test_mode=True,
                           now=datetime.now(timezone.utc), artist_display_name="Kay Lune")
    order["stripe_session_id"] = SID
    db._db.orders.insert_one(dict(order))
    sessions = FakeStripeSessions()
    sessions.order_id = order["order_id"]
    monkeypatch.setattr(so, "stripe_client", lambda: SimpleNamespace(
        v1=SimpleNamespace(checkout=SimpleNamespace(sessions=sessions))))
    puts = []

    async def fake_put(key, data, content_type):
        puts.append(key)

    monkeypatch.setattr(server, "db", db)
    monkeypatch.setattr(server, "_r2_put", fake_put)
    monkeypatch.setattr(server.limiter, "enabled", False)
    yield SimpleNamespace(client=TestClient(server.app), db=db, order=order, sessions=sessions, puts=puts)


def get(env):
    return env.db._db.orders.find_one({"order_id": env.order["order_id"]}, {"_id": 0})


def poll(env, sid=SID):
    return env.client.get(f"/api/sync/orders/by-session/{sid}")


def fulfilled_token(env):
    r = poll(env)
    assert r.json()["status"] == "ready", r.text
    return r.json()["download_token"]


def test_fallback_delivers_when_webhook_is_late(env):
    r = poll(env)
    body = r.json()
    assert r.status_code == 200 and body["status"] == "ready" and body["download_token"]
    assert get(env)["status"] == "fulfilled" and env.puts and env.sessions.calls == 1


def test_success_view_hides_buyer_details(env):
    r = poll(env)
    text = r.text
    for secret in ("Dana Secret", "Secret Co", "dana@secret.example", "pi_9", "order_id"):
        assert secret not in text
    # Brief 17: only a masked email is exposed, enough for the signed-out account nudge.
    assert r.json()["buyer_email_masked"] == "d****@secret.example"


def test_unpaid_session_stays_processing_and_stripe_is_throttled(env):
    env.sessions.payment_status = "unpaid"
    assert poll(env).json()["status"] == "processing"
    assert poll(env).json()["status"] == "processing"
    assert env.sessions.calls == 1  # second poll inside the recheck window did not call Stripe


def test_recheck_allowed_again_after_window(env):
    env.sessions.payment_status = "unpaid"
    poll(env)
    old = (datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat()
    env.db._db.orders.update_one({"order_id": env.order["order_id"]}, {"$set": {"stripe_checked_at": old}})
    env.sessions.payment_status = "paid"
    assert poll(env).json()["status"] == "ready" and env.sessions.calls == 2


def test_refresh_returns_same_link(env):
    assert fulfilled_token(env) == poll(env).json()["download_token"]


@pytest.mark.parametrize("sid", ["cs_test_nope0000000", "not-a-session", "cs_test_" + "a" * 300])
def test_unknown_or_malformed_session_is_404(env, sid):
    assert poll(env, sid).status_code == 404


@pytest.mark.parametrize("status", ["failed", "refunded"])
def test_failed_and_refunded_statuses_have_no_link(env, status):
    env.db._db.orders.update_one({"order_id": env.order["order_id"]}, {"$set": {"status": status}})
    body = poll(env).json()
    assert body["status"] == status and body["download_token"] is None and env.sessions.calls == 0


def test_listing_shows_files_and_remaining(env):
    token = fulfilled_token(env)
    r = env.client.get(f"/api/sync/downloads/{token}")
    body = r.json()
    assert r.status_code == 200 and body["test_mode"] is True
    assert [f["name"] for f in body["files"]] == ["license", "master", *so.STEM_NAMES]
    assert all(f["remaining"] == 10 for f in body["files"])
    assert "dana" not in r.text.lower()


def test_download_signs_attachment_and_counts(env):
    token = fulfilled_token(env)
    r = env.client.post(f"/api/sync/downloads/{token}/master")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["filename"] == f"Kay Lune - Night Drive ({env.order['license_id']}) master.wav"
    q = parse_qs(urlparse(body["url"]).query)
    assert "attachment" in unquote(q["response-content-disposition"][0])
    assert "catalog/a/b/mastered/t1.wav" in unquote(urlparse(body["url"]).path)
    assert get(env)["download_counts"] == {"master": 1}


def test_per_file_limit(env, monkeypatch):
    monkeypatch.setenv("SYNC_DOWNLOAD_MAX_PER_FILE", "2")
    token = fulfilled_token(env)
    assert env.client.post(f"/api/sync/downloads/{token}/vocals").status_code == 200
    assert env.client.post(f"/api/sync/downloads/{token}/vocals").status_code == 200
    assert env.client.post(f"/api/sync/downloads/{token}/vocals").status_code == 429
    assert env.client.post(f"/api/sync/downloads/{token}/drums").status_code == 200


def test_unknown_file_and_unbought_stems(env):
    token = fulfilled_token(env)
    assert env.client.post(f"/api/sync/downloads/{token}/secrets").status_code == 404
    env.db._db.orders.update_one({"order_id": env.order["order_id"]}, {"$set": {"include_stems": False}})
    assert env.client.post(f"/api/sync/downloads/{token}/vocals").status_code == 404


def test_bad_expired_and_refunded_tokens(env):
    token = fulfilled_token(env)
    assert env.client.get("/api/sync/downloads/wrongtoken").status_code == 404
    past = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    env.db._db.orders.update_one({"order_id": env.order["order_id"]}, {"$set": {"token_expires_at": past}})
    assert env.client.get(f"/api/sync/downloads/{token}").status_code == 404
    env.db._db.orders.update_one({"order_id": env.order["order_id"]},
                                 {"$set": {"token_expires_at": "2099-01-01T00:00:00+00:00", "status": "refunded"}})
    assert env.client.post(f"/api/sync/downloads/{token}/master").status_code == 404


def test_missing_master_is_409(env):
    token = fulfilled_token(env)
    env.db._db.track_submissions.update_one({"id": "t1"}, {"$unset": {"mastered_r2_key": ""}})
    assert env.client.get(f"/api/sync/downloads/{token}").status_code == 409


def test_filename_is_ascii_safe():
    order = {"artist_display_name": 'Bad"Name/\\<x>', "track_title": "Café\nNight", "license_id": "OVX-1"}
    name = so.download_filename(order, "master", "k/x.WAV")
    assert name == "BadNamex - CafNight (OVX-1) master.wav"
