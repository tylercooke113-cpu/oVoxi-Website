"""Sync checkout: pricing, configuration and access rules. See docs/PRD-03 sections 7 and 12.

Prices are computed here and only here (decision 27). The client never sends a price.
Configuration is read from the environment at call time, so a Railway variable change
takes effect on the next request without a code change.
"""
import base64
import hashlib
import hmac
import os
import re
import secrets
import uuid
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

TIERS = {
    "creator": ("Creator", "SYNC_PRICE_CREATOR", 1900),
    "creator_pro": ("Creator Pro", "SYNC_PRICE_CREATOR_PRO", 4900),
    "business_social": ("Business Social", "SYNC_PRICE_BUSINESS_SOCIAL", 14900),
}
CURRENCY = "usd"

# Buyer-facing one-liners for the license modal. Placeholders until counsel defines each tier's scope.
TIER_DESCRIPTIONS = {"creator": "Test", "creator_pro": "Test", "business_social": "Test"}


class ConfigError(RuntimeError):
    """Server misconfiguration. Endpoints map this to 503 and log the message."""


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ConfigError(f"{name} must be an integer, got {raw!r}")
    if value <= 0:
        raise ConfigError(f"{name} must be positive, got {value}")
    return value


def _env_flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if not raw:
        return default
    return raw == "true"


def stems_uplift() -> Decimal:
    raw = os.environ.get("SYNC_STEMS_UPLIFT", "").strip() or "0.22"
    try:
        value = Decimal(raw)
    except Exception:
        raise ConfigError(f"SYNC_STEMS_UPLIFT must be a number, got {raw!r}")
    if value < 0 or value > 5:
        raise ConfigError(f"SYNC_STEMS_UPLIFT out of range: {value}")
    return value


def tier_label(tier: str) -> str:
    if tier not in TIERS:
        raise ValueError(f"Unknown tier {tier!r}")
    return TIERS[tier][0]


def price_cents(tier: str, include_stems: bool) -> int:
    """License price in cents, before tax. Stems add the uplift, rounded to the nearest dollar."""
    if tier not in TIERS:
        raise ValueError(f"Unknown tier {tier!r}")
    _, env_name, default = TIERS[tier]
    base = _env_int(env_name, default)
    if not include_stems:
        return base
    dollars = (Decimal(base) * (1 + stems_uplift()) / 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return int(dollars) * 100


def checkout_enabled() -> bool:
    return _env_flag("SYNC_CHECKOUT_ENABLED", False)


def deliver_stems() -> bool:
    return _env_flag("SYNC_DELIVER_STEMS", True)


def download_ttl_days() -> int:
    return _env_int("SYNC_DOWNLOAD_TTL_DAYS", 30)


def download_max_per_file() -> int:
    return _env_int("SYNC_DOWNLOAD_MAX_PER_FILE", 10)


def terms_version() -> str:
    return os.environ.get("SYNC_TERMS_VERSION", "").strip() or "draft-0"


def stripe_tax_code() -> str | None:
    return os.environ.get("SYNC_STRIPE_TAX_CODE", "").strip() or None


def stripe_secret_key() -> str:
    key = os.environ.get("STRIPE_SECRET_KEY", "").strip()
    if not key:
        raise ConfigError("STRIPE_SECRET_KEY is not set")
    return key


def stripe_webhook_secret() -> str:
    secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "").strip()
    if not secret:
        raise ConfigError("STRIPE_WEBHOOK_SECRET is not set")
    return secret


def token_secret() -> bytes:
    secret = os.environ.get("SYNC_TOKEN_SECRET", "").strip()
    if len(secret) < 32:
        raise ConfigError("SYNC_TOKEN_SECRET is missing or shorter than 32 characters")
    return secret.encode()


def is_test_key() -> bool:
    return stripe_secret_key().startswith(("sk_test_", "rk_test_"))


def can_checkout(is_admin: bool) -> bool:
    """Decision 25: public checkout only when enabled; before that, admins with a test key only."""
    if checkout_enabled():
        return True
    return is_admin and is_test_key()


# ---------------------------------------------------------------------------
# Orders, download tokens and indexes (PRD-03 7.3, 8.4, 8.5; decision 26)
# ---------------------------------------------------------------------------

STEM_NAMES = ("vocals", "instrumental", "drums", "bass", "other")
_LICENSE_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"  # Crockford base32: no I, L, O, U


class DeliveryError(RuntimeError):
    """A paid order cannot be delivered (a file is missing). Logged and left in `paid` for retry."""


def derive_token(order_id: str, version: int) -> str:
    """Download token for an order. Rebuildable from the secret, so nothing secret is stored."""
    digest = hmac.new(token_secret(), f"{order_id}:{version}".encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def new_license_id() -> str:
    return "OVX-" + "".join(secrets.choice(_LICENSE_ALPHABET) for _ in range(10))


def build_order(*, track: dict, tier: str, include_stems: bool, buyer_name: str,
                buyer_company: str, buyer_email: str, test_mode: bool, now: datetime,
                track_title: str = "", artist_display_name: str = "") -> dict:
    """A new `pending` order. The price is computed here, never taken from the request."""
    if include_stems and not deliver_stems():
        raise ValueError("Stems are not available")
    return {
        "order_id": uuid.uuid4().hex,
        "license_id": new_license_id(),
        "track_id": track["id"],
        "track_title": track_title or track.get("track_name") or "",
        "artist_display_name": artist_display_name or track.get("artist_name") or "",
        "artist_user_id": track.get("clerk_user_id"),
        "tier": tier,
        "include_stems": bool(include_stems),
        "price_cents": price_cents(tier, include_stems),
        "tax_cents": None,
        "amount_total_cents": None,
        "currency": CURRENCY,
        "buyer_name": buyer_name,
        "buyer_company": buyer_company or "",
        "buyer_email": buyer_email,
        "terms_version": terms_version(),
        "stripe_session_id": None,
        "stripe_payment_intent": None,
        "status": "pending",
        "download_token_hash": None,
        "token_version": 0,
        "token_expires_at": None,
        "download_counts": {},
        "license_pdf_key": None,
        "email_status": None,
        "refunds": [],
        "test_mode": bool(test_mode),
        "created_at": now.isoformat(),
        "paid_at": None,
        "fulfilled_at": None,
        "refunded_at": None,
    }


def delivery_files(order: dict, track: dict) -> dict:
    """File name -> R2 key for the download page. Delivers what was bought, whatever the flags say now."""
    files = {"license": order.get("license_pdf_key"), "master": track.get("mastered_r2_key")}
    if order.get("include_stems"):
        stems = track.get("stem_paths") or {}
        for name in STEM_NAMES:
            files[name] = stems.get(name)
    missing = sorted(name for name, key in files.items() if not key)
    if missing:
        raise DeliveryError(f"order {order.get('order_id')} missing files: {', '.join(missing)}")
    return files


# Status transitions. Each is conditional on the prior status, so a repeated
# webhook or a race between the webhook and the success-page fallback is a no-op.
# Each returns True only for the caller that made the change.

async def mark_paid(db, order_id: str, *, payment_intent, tax_cents, amount_total_cents, now: datetime) -> bool:
    res = await db.orders.update_one(
        {"order_id": order_id, "status": "pending"},
        {"$set": {"status": "paid", "stripe_payment_intent": payment_intent, "tax_cents": tax_cents,
                  "amount_total_cents": amount_total_cents, "paid_at": now.isoformat()}})
    return res.modified_count == 1


async def mark_fulfilled(db, order_id: str, *, license_pdf_key: str, now: datetime) -> bool:
    version = 1
    token = derive_token(order_id, version)
    res = await db.orders.update_one(
        {"order_id": order_id, "status": "paid"},
        {"$set": {"status": "fulfilled", "license_pdf_key": license_pdf_key, "token_version": version,
                  "download_token_hash": hash_token(token),
                  "token_expires_at": (now + timedelta(days=download_ttl_days())).isoformat(),
                  "fulfilled_at": now.isoformat()}})
    return res.modified_count == 1


async def mark_failed(db, order_id: str, *, now: datetime) -> bool:
    res = await db.orders.update_one(
        {"order_id": order_id, "status": "pending"},
        {"$set": {"status": "failed", "failed_at": now.isoformat()}})
    return res.modified_count == 1


async def reissue_token(db, order_id: str, *, now: datetime) -> str | None:
    """New link, old one dead, download counts reset. Fulfilled orders only (admin action, 6c)."""
    order = await db.orders.find_one({"order_id": order_id, "status": "fulfilled"})
    if not order:
        return None
    version = int(order.get("token_version") or 0) + 1
    token = derive_token(order_id, version)
    res = await db.orders.update_one(
        {"order_id": order_id, "status": "fulfilled", "token_version": order.get("token_version")},
        {"$set": {"token_version": version, "download_token_hash": hash_token(token), "download_counts": {},
                  "token_expires_at": (now + timedelta(days=download_ttl_days())).isoformat()}})
    return token if res.modified_count == 1 else None


def current_token(order: dict) -> str | None:
    """The live download token for a fulfilled order, for the success page."""
    if order.get("status") != "fulfilled" or not order.get("token_version"):
        return None
    return derive_token(order["order_id"], int(order["token_version"]))


async def find_by_token(db, token: str, *, now: datetime) -> dict | None:
    """A fulfilled, unexpired order for this token, or None. Refunded orders never match."""
    if not token or len(token) > 100:
        return None
    order = await db.orders.find_one({"download_token_hash": hash_token(token), "status": "fulfilled"})
    if not order or not order.get("token_expires_at"):
        return None
    if datetime.fromisoformat(order["token_expires_at"]) <= now:
        return None
    return order


async def ensure_indexes(db) -> None:
    await db.orders.create_index([("order_id", 1)], unique=True)
    await db.orders.create_index([("license_id", 1)], unique=True)
    await db.orders.create_index([("stripe_session_id", 1)], unique=True,
                                 partialFilterExpression={"stripe_session_id": {"$type": "string"}})
    await db.orders.create_index([("stripe_payment_intent", 1)],
                                 partialFilterExpression={"stripe_payment_intent": {"$type": "string"}})
    await db.orders.create_index([("download_token_hash", 1)], unique=True,
                                 partialFilterExpression={"download_token_hash": {"$type": "string"}})
    await db.orders.create_index([("artist_user_id", 1), ("created_at", -1)])
    await db.orders.create_index([("status", 1), ("created_at", -1)])
    await db.stripe_events.create_index([("event_id", 1)], unique=True)


# ---------------------------------------------------------------------------
# Stripe Checkout Session (PRD-03 7.2 step 3; decisions 27 and 29)
# ---------------------------------------------------------------------------
CHECKOUT_EXPIRY_MINUTES = 35  # Stripe requires at least 30; margin for clock skew


def site_url() -> str:
    url = (os.environ.get("SYNC_SITE_URL", "").strip() or "https://ovoxi.net").rstrip("/")
    if not (url.startswith("https://") or url.startswith("http://localhost")):
        raise ConfigError(f"SYNC_SITE_URL must be https, got {url!r}")
    return url


def stripe_client():
    import stripe  # imported lazily so modules that never touch Stripe do not need it
    return stripe.StripeClient(stripe_secret_key())


def checkout_session_params(order: dict, *, now: datetime) -> dict:
    """Parameters for stripe checkout.sessions.create. Price is the order's, set by build_order."""
    name = f"Sync license: {order['track_title']} by {order['artist_display_name']}"
    tier = tier_label(order["tier"]) + (" + stems" if order["include_stems"] else "")
    product = {"name": name[:250], "description": f"{tier}. License {order['license_id']}.",
               "metadata": {"track_id": order["track_id"], "tier": order["tier"]}}
    code = stripe_tax_code()
    if code:
        product["tax_code"] = code
    meta = {"order_id": order["order_id"], "license_id": order["license_id"], "track_id": order["track_id"]}
    base = site_url()
    return {
        "mode": "payment",
        "line_items": [{"quantity": 1, "price_data": {
            "currency": order["currency"], "unit_amount": order["price_cents"],
            "tax_behavior": "exclusive", "product_data": product}}],
        "customer_email": order["buyer_email"],
        "billing_address_collection": "required",
        "automatic_tax": {"enabled": True},
        "client_reference_id": order["order_id"],
        "metadata": meta,
        "payment_intent_data": {"metadata": meta},
        "expires_at": int((now + timedelta(minutes=CHECKOUT_EXPIRY_MINUTES)).timestamp()),
        "success_url": f"{base}/sync/success?session_id={{CHECKOUT_SESSION_ID}}",
        "cancel_url": f"{base}/sync/track/{order['track_id']}?checkout=cancelled",
    }


# ---------------------------------------------------------------------------
# Payment events and fulfilment (PRD-03 7.2 steps 5-6, 7.5; decisions 26 and 28)
# ---------------------------------------------------------------------------

def license_pdf_key(order: dict) -> str:
    return f"licenses/{order['order_id']}/{order['license_id']}.pdf"


async def apply_session_paid(db, session: dict, *, now: datetime) -> str | None:
    """pending -> paid from a Checkout Session. Returns the order_id to fulfil, or None.

    Used by the webhook and by the success-page fallback. Does nothing unless Stripe
    says the payment is complete (delayed methods arrive later as async_payment_succeeded).
    """
    order_id = (session.get("metadata") or {}).get("order_id")
    if not order_id:
        return None
    order = await db.orders.find_one({"order_id": order_id})
    if not order:
        return None
    if order.get("stripe_session_id") and order["stripe_session_id"] != session.get("id"):
        return None  # metadata points at an order that belongs to a different session
    if session.get("payment_status") != "paid":
        return None
    tax = (session.get("total_details") or {}).get("amount_tax")
    subtotal = session.get("amount_subtotal")
    if subtotal is not None and subtotal != order["price_cents"]:
        await db.orders.update_one({"order_id": order_id}, {"$set": {"amount_mismatch": True}})
    await mark_paid(db, order_id, payment_intent=session.get("payment_intent"), tax_cents=tax,
                    amount_total_cents=session.get("amount_total"), now=now)
    if not order.get("stripe_session_id"):
        await db.orders.update_one({"order_id": order_id, "stripe_session_id": None},
                                   {"$set": {"stripe_session_id": session.get("id")}})
    return order_id


async def apply_session_expired(db, session: dict, *, now: datetime) -> None:
    order_id = (session.get("metadata") or {}).get("order_id")
    if order_id:
        await mark_failed(db, order_id, now=now)


async def apply_refund(db, charge: dict, *, now: datetime) -> str | None:
    """Record a refund. Only a full refund revokes the license (decision 28). Returns the order_id."""
    pi = charge.get("payment_intent")
    if not pi:
        return None
    order = await db.orders.find_one({"stripe_payment_intent": pi})
    if not order:
        return None
    refunded = int(charge.get("amount_refunded") or 0)
    full = charge.get("refunded") is True or refunded >= int(charge.get("amount") or 0) > 0
    await db.orders.update_one({"order_id": order["order_id"]},
                               {"$push": {"refunds": {"amount_refunded_cents": refunded, "full": full,
                                                      "at": now.isoformat()}}})
    if not full:
        return order["order_id"]
    res = await db.orders.update_one(
        {"order_id": order["order_id"], "status": {"$in": ["paid", "fulfilled"]}},
        {"$set": {"status": "refunded", "refunded_at": now.isoformat()}})
    if res.modified_count == 1 and order.get("status") == "fulfilled" and not order.get("test_mode"):
        await db.sync_profiles.update_one({"user_id": order["artist_user_id"], "sales_count": {"$gt": 0}},
                                          {"$inc": {"sales_count": -1}})
    return order["order_id"]


async def fulfil_order(db, order_id: str, *, render_pdf, put_object, now: datetime) -> str:
    """paid -> fulfilled: license PDF to R2, download token, popularity count. Safe to repeat.

    render_pdf(order, track_title, artist_name) -> bytes and put_object(key, data, content_type)
    are passed in so this module has no R2 or ReportLab dependency. Returns the resulting status.
    """
    order = await db.orders.find_one({"order_id": order_id})
    if not order:
        return "missing"
    if order["status"] != "paid":
        return order["status"]
    track = await db.track_submissions.find_one({"id": order["track_id"]}) or {}
    key = license_pdf_key(order)
    delivery_files(dict(order, license_pdf_key=key), track)  # DeliveryError before any upload
    pdf = await render_pdf(order, order.get("track_title") or track.get("track_name") or "",
                           order.get("artist_display_name") or track.get("artist_name") or "")
    await put_object(key, pdf, "application/pdf")
    if await mark_fulfilled(db, order_id, license_pdf_key=key, now=now):
        await db.orders.update_one({"order_id": order_id}, {"$set": {"email_status": "skipped"}})
        if not order.get("test_mode"):
            await db.sync_profiles.update_one({"user_id": order["artist_user_id"]}, {"$inc": {"sales_count": 1}})
    return "fulfilled"


async def event_seen(db, event_id: str) -> bool:
    return await db.stripe_events.find_one({"event_id": event_id}) is not None


async def record_event(db, event_id: str, event_type: str, *, now: datetime) -> None:
    try:
        await db.stripe_events.insert_one({"event_id": event_id, "type": event_type,
                                           "processed_at": now.isoformat()})
    except Exception as exc:  # duplicate from a concurrent delivery of the same event
        if "duplicate" not in str(exc).lower() and "E11000" not in str(exc):
            raise


# ---------------------------------------------------------------------------
# Success page and download page (PRD-03 7.2 step 6, 7.3)
# ---------------------------------------------------------------------------
SESSION_ID_RE = re.compile(r"^cs_(test|live)_[A-Za-z0-9]{10,250}$")
STRIPE_RECHECK_SECONDS = 5
DOWNLOAD_URL_TTL_SECONDS = 300
FILE_LABELS = {"license": "License certificate (PDF)", "master": "Master (24-bit WAV)",
               "vocals": "Stem: vocals", "instrumental": "Stem: instrumental", "drums": "Stem: drums",
               "bass": "Stem: bass", "other": "Stem: other"}
PUBLIC_STATUS = {"pending": "processing", "paid": "processing", "fulfilled": "ready",
                 "failed": "failed", "refunded": "refunded"}


def success_view(order: dict) -> dict:
    """What the success page may see: no buyer name, email or company."""
    view = {"status": PUBLIC_STATUS.get(order.get("status"), "processing"),
            "license_id": order.get("license_id"), "track_title": order.get("track_title"),
            "artist_display_name": order.get("artist_display_name"), "tier": order.get("tier"),
            "include_stems": bool(order.get("include_stems")), "download_token": None}
    if view["status"] == "ready":
        view["download_token"] = current_token(order)
    return view


async def claim_stripe_recheck(db, order_id: str, *, now: datetime) -> bool:
    """At most one Stripe lookup per order every few seconds, however often the page polls."""
    cutoff = (now - timedelta(seconds=STRIPE_RECHECK_SECONDS)).isoformat()
    res = await db.orders.update_one(
        {"order_id": order_id, "status": "pending",
         "$or": [{"stripe_checked_at": None}, {"stripe_checked_at": {"$lt": cutoff}}]},
        {"$set": {"stripe_checked_at": now.isoformat()}})
    return res.modified_count == 1


def download_listing(order: dict, files: dict) -> dict:
    limit = download_max_per_file()
    counts = order.get("download_counts") or {}
    return {
        "license_id": order["license_id"], "track_title": order.get("track_title"),
        "artist_display_name": order.get("artist_display_name"), "tier": order["tier"],
        "include_stems": bool(order.get("include_stems")), "expires_at": order.get("token_expires_at"),
        "test_mode": bool(order.get("test_mode")),
        "files": [{"name": name, "label": FILE_LABELS.get(name, name),
                   "remaining": max(0, limit - int(counts.get(name, 0)))} for name in files],
    }


async def claim_download(db, order: dict, name: str) -> bool:
    """Atomically count one download of `name`; False when the per-file limit is reached."""
    field = f"download_counts.{name}"
    res = await db.orders.update_one(
        {"order_id": order["order_id"], "status": "fulfilled",
         "download_token_hash": order["download_token_hash"],
         "$or": [{field: {"$exists": False}}, {field: {"$lt": download_max_per_file()}}]},
        {"$inc": {field: 1}})
    return res.modified_count == 1


def download_filename(order: dict, name: str, key: str) -> str:
    """ASCII-safe attachment name, e.g. 'Kay Lune - Night Drive (OVX-7K2M9Q4XRT) master.wav'."""
    ext = key.rsplit(".", 1)[-1].lower() if "." in key else "bin"
    raw = f"{order.get('artist_display_name', '')} - {order.get('track_title', '')} ({order['license_id']}) {name}"
    safe = re.sub(r"[^A-Za-z0-9 ._()-]", "", raw)
    safe = re.sub(r"\s+", " ", safe).strip()[:150] or order["license_id"]
    return f"{safe}.{ext}"


# ---------------------------------------------------------------------------
# Public checkout configuration for the license modal (PRD-03 6b)
# ---------------------------------------------------------------------------

def checkout_config(*, is_admin: bool, terms_text: dict) -> dict:
    """What the License button and modal need. Only `can_checkout: False` when the viewer
    cannot buy, so nothing else is exposed before launch. Never raises ConfigError."""
    try:
        if not can_checkout(is_admin):
            return {"can_checkout": False}
        token_secret()
        version = terms_version()
        stems = deliver_stems()
        tiers = [{"id": tid, "label": label, "description": TIER_DESCRIPTIONS.get(tid, ""),
                  "price_cents": price_cents(tid, False),
                  "price_with_stems_cents": price_cents(tid, True) if stems else None}
                 for tid, (label, _, _) in TIERS.items()]
        return {"can_checkout": True, "test_mode": is_test_key(), "currency": CURRENCY,
                "stems_available": stems, "terms_version": version,
                "terms": list(terms_text[version]), "tiers": tiers}
    except (ConfigError, KeyError):
        return {"can_checkout": False}
