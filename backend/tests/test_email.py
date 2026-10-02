"""PRD-03 Phase 6c: email_sender (Resend over httpx), the license email content, and
the license email during fulfilment."""
import asyncio
import base64
import json
from datetime import datetime, timezone

import httpx
import pytest

import email_sender
import sync_orders as so
from sync_emails import license_email

NOW = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def email_env(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "re_test_key")
    monkeypatch.setenv("EMAIL_FROM", "oVoxi Licenses <licenses@mail.ovoxi.net>")
    monkeypatch.setenv("EMAIL_REPLY_TO", "tyler@ovoxi.net")


def send(transport, **kw):
    args = dict(to="d@example.com", subject="S", html="<p>h</p>", text="t")
    args.update(kw)
    return asyncio.run(email_sender.send_email(transport=transport, **args))


def test_sends_to_resend_with_attachment_and_idempotency():
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["headers"] = request.headers
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"id": "email_123"})

    r = send(httpx.MockTransport(handler), attachments=[("a.pdf", b"%PDF-1")], idempotency_key="license-o1-v1")
    assert r == {"status": "sent", "id": "email_123", "error": None}
    assert seen["url"] == "https://api.resend.com/emails"
    assert seen["headers"]["authorization"] == "Bearer re_test_key"
    assert seen["headers"]["idempotency-key"] == "license-o1-v1"
    b = seen["body"]
    assert b["from"] == "oVoxi Licenses <licenses@mail.ovoxi.net>" and b["to"] == ["d@example.com"]
    assert b["reply_to"] == "tyler@ovoxi.net"
    assert b["attachments"] == [{"filename": "a.pdf", "content": base64.b64encode(b"%PDF-1").decode()}]


def test_provider_error_is_failed_not_raised():
    r = send(httpx.MockTransport(lambda req: httpx.Response(422, json={"message": "bad from"})))
    assert r["status"] == "failed" and "422" in r["error"]


def test_network_error_is_failed_not_raised():
    def boom(request):
        raise httpx.ConnectError("down")
    r = send(httpx.MockTransport(boom))
    assert r["status"] == "failed" and "ConnectError" in r["error"]


@pytest.mark.parametrize("missing", ["RESEND_API_KEY", "EMAIL_FROM"])
def test_unconfigured_is_skipped_without_network(monkeypatch, missing):
    monkeypatch.delenv(missing)
    called = []
    r = send(httpx.MockTransport(lambda req: called.append(1) or httpx.Response(200)))
    assert r["status"] == "skipped" and called == []
    assert email_sender.email_configured() is False


ORDER = {"order_id": "o1", "license_id": "OVX-ABC", "track_title": "Night Drive", "artist_display_name": "Kay Lune",
         "tier": "creator_pro", "include_stems": True, "token_expires_at": "2026-10-30T12:00:00+00:00",
         "test_mode": False}


def test_license_email_content():
    subject, html, text = license_email(ORDER, download_url="https://ovoxi.net/license/tok")
    assert subject == "Your license for Night Drive"
    for s in ("Night Drive", "Kay Lune", "Creator Pro + stems", "OVX-ABC", "https://ovoxi.net/license/tok",
              "October 30, 2026"):
        assert s in html and s in text
    assert "test order" not in text.lower()


def test_test_order_is_marked():
    subject, html, text = license_email(dict(ORDER, test_mode=True), download_url="u")
    assert subject.startswith("[TEST] ") and "not a valid license" in text and "not a valid license" in html


def test_reissue_wording():
    subject, _, text = license_email(ORDER, download_url="u", reissued=True)
    assert subject.endswith("(new download link)") and "new download link" in text


def test_user_text_is_escaped_in_html():
    evil = dict(ORDER, track_title='<script>x</script>', artist_display_name='"><img src=x>')
    _, html, text = license_email(evil, download_url='https://ovoxi.net/license/a"b')
    assert "<script>" not in html and "<img" not in html and 'a"b' not in html
    assert "<script>x</script>" in text  # plain text keeps it literally


# --- fulfilment sends exactly one email and never lets email undo delivery ---

from test_sync_orders import AsyncDB  # noqa: E402


def paid_order(db, monkeypatch):
    monkeypatch.setenv("SYNC_TOKEN_SECRET", "s" * 64)
    track = {"id": "t1", "clerk_user_id": "a1", "mastered_r2_key": "m.wav"}
    db._db.track_submissions.insert_one(dict(track))
    db._db.sync_profiles.insert_one({"user_id": "a1", "sales_count": 0})
    o = so.build_order(track=track, tier="creator", include_stems=False, buyer_name="B", buyer_company="",
                       buyer_email="b@example.com", test_mode=False, now=NOW)
    o["status"] = "paid"
    db._db.orders.insert_one(dict(o))
    return o


async def _pdf(order, title, artist, lic=None):
    return b"%PDF-x"


async def _put(key, data, ct):
    return None


def fulfil(db, oid, sender):
    return asyncio.run(so.fulfil_order(db, oid, render_pdf=_pdf, put_object=_put, now=NOW, send_license=sender))


def test_fulfil_sends_once_and_records(monkeypatch):
    db = AsyncDB()
    o = paid_order(db, monkeypatch)
    calls = []

    async def sender(order, pdf):
        calls.append((order["status"], pdf))
        return {"status": "sent", "id": "email_1", "error": None}

    assert fulfil(db, o["order_id"], sender) == "fulfilled"
    assert fulfil(db, o["order_id"], sender) == "fulfilled"
    assert calls == [("fulfilled", b"%PDF-x")]
    saved = db._db.orders.find_one({"order_id": o["order_id"]})
    assert saved["email_status"] == "sent" and saved["email_id"] == "email_1"


def test_email_crash_keeps_order_fulfilled(monkeypatch):
    db = AsyncDB()
    o = paid_order(db, monkeypatch)

    async def sender(order, pdf):
        raise RuntimeError("smtp on fire")

    assert fulfil(db, o["order_id"], sender) == "fulfilled"
    saved = db._db.orders.find_one({"order_id": o["order_id"]})
    assert saved["status"] == "fulfilled" and saved["email_status"] == "failed"
    assert "smtp on fire" in saved["email_error"]
    assert db._db.sync_profiles.find_one({"user_id": "a1"})["sales_count"] == 1
