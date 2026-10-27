"""Brief 27 Part D: the Vault Wallet API and co-owner lines moving to their account."""
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import cosign
import payouts
import server
import wallet
from test_subscriptions import AsyncDB, run

CO = {"sub": "user_co", "metadata": {}}


def line(payee, amount, status="accrued", src="o1", period="2026-11", test_mode=True):
    return {"id": f"{payee}-{src}", "payee_key": payee, "payee_user_id": None, "payee_email": "jordan@example.com",
            "roles": ["writer"], "share_bp": 5000, "source_type": "order", "source_id": src, "track_id": "t1",
            "field": "sync", "period": period, "net_cents": 9680, "rate_bp": 3300, "amount_cents": amount,
            "status": status, "payout_id": None, "test_mode": test_mode, "created_at": f"{period}-05T00:00:00+00:00"}


@pytest.fixture
def env(monkeypatch):
    db = AsyncDB()
    run(wallet.ensure_indexes(db))
    run(payouts.ensure_indexes(db))
    run(db.track_submissions.insert_one({"id": "t1", "track_name": "Night Drive", "clerk_user_id": "user_a"}))
    monkeypatch.setattr(server, "db", db)
    monkeypatch.setattr(server.limiter, "enabled", False)
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_1")
    verified = {"v": True}

    async def clerk_user(uid):
        return {"email": "Jordan@Example.com", "email_verified": verified["v"]}
    monkeypatch.setattr(server, "fetch_clerk_user", clerk_user)
    server.app.dependency_overrides[server.verify_clerk_token] = lambda: CO
    yield SimpleNamespace(db=db, client=TestClient(server.app), verified=verified)
    server.app.dependency_overrides.clear()


def test_verified_sign_up_claims_the_email_lines(env):
    run(env.db.wallet_entries.insert_one(line("email:jordan@example.com", 1597)))
    run(env.db.wallet_entries.insert_one(line("email:jordan@example.com", 400, src="o2", status="available")))
    run(env.db.wallet_entries.insert_one(line("email:someone@else.com", 999, src="o3")))
    r = env.client.get("/api/wallet/me").json()
    assert [e["amount_cents"] for e in r["entries"]] == [1597, 400]
    assert r["entries"][0]["track_title"] == "Night Drive" and r["entries"][0]["kind"] == "Sync license"
    assert r["summary"]["available_cents"] == 400 and r["summary"]["pending_cents"] == 1597
    assert r["connect"] == {"connected": False} and r["minimum_cents"] == 2500
    moved = run(env.db.wallet_entries.find_one({"source_id": "o1"}))
    assert moved["payee_key"] == "user_co" and moved["claimed_from"] == "email:jordan@example.com"


def test_unverified_email_claims_nothing(env):
    env.verified["v"] = False
    run(env.db.wallet_entries.insert_one(line("email:jordan@example.com", 1597)))
    assert env.client.get("/api/wallet/me").json()["entries"] == []


def test_claim_skips_a_line_the_account_already_has(env):
    run(env.db.wallet_entries.insert_one(line("email:jordan@example.com", 100)))
    run(env.db.wallet_entries.insert_one({**line("user_co", 200), "id": "dup"}))
    assert run(wallet.claim_email_entries(env.db, user_id="user_co", email="jordan@example.com")) == 0


def test_other_stripe_mode_lines_are_hidden(env):
    run(env.db.wallet_entries.insert_one(line("user_co", 500, test_mode=False)))
    assert env.client.get("/api/wallet/me").json()["entries"] == []


def test_statement_download_is_the_owners_only(env, monkeypatch):
    run(env.db.statements.insert_one({"payee_key": "user_co", "period": "2026-11", "test_mode": True,
                                      "pdf_key": "statements/user_co/2026-11-test.pdf"}))
    monkeypatch.setattr(server, "r2_client", SimpleNamespace(
        generate_presigned_url=lambda op, Params, ExpiresIn: f"https://r2.test/{Params['Key']}"))
    assert env.client.get("/api/wallet/statements/2026-11").json()["url"].endswith("2026-11-test.pdf")
    assert env.client.get("/api/wallet/statements/2026-10").status_code == 404
    assert env.client.get("/api/wallet/statements/bad").status_code == 404


def test_cosign_email_mentions_the_wallet():
    subject, html, text = cosign.signed_copy_email(work_title="Night Drive")
    assert cosign.WALLET_NOTE in text and cosign.WALLET_NOTE in html
