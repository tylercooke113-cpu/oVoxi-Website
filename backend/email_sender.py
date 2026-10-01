"""Outbound email (PRD-03 10). The only module that knows the provider, so switching
from Resend is a change to this file alone.

Configuration: RESEND_API_KEY, EMAIL_FROM, EMAIL_REPLY_TO. When the key or sender is
missing, sending is skipped (status "skipped"), never an error: email is a convenience,
delivery always works through the success page.
"""
import base64
import os

import httpx

RESEND_URL = "https://api.resend.com/emails"
TIMEOUT_SECONDS = 10


def _config():
    key = os.environ.get("RESEND_API_KEY", "").strip()
    sender = os.environ.get("EMAIL_FROM", "").strip()
    reply_to = os.environ.get("EMAIL_REPLY_TO", "").strip()
    return key, sender, reply_to


def email_configured() -> bool:
    key, sender, _ = _config()
    return bool(key and sender)


async def send_email(*, to: str, subject: str, html: str, text: str, attachments=None,
                     idempotency_key: str | None = None, transport: httpx.AsyncBaseTransport | None = None) -> dict:
    """Send one email. Returns {"status": "sent"|"failed"|"skipped", "id", "error"}; never raises.

    attachments: list of (filename, bytes). idempotency_key stops a retried call from
    sending the same email twice. transport is for tests.
    """
    key, sender, reply_to = _config()
    if not (key and sender):
        return {"status": "skipped", "id": None, "error": "email not configured"}
    body = {"from": sender, "to": [to], "subject": subject, "html": html, "text": text}
    if reply_to:
        body["reply_to"] = reply_to
    if attachments:
        body["attachments"] = [{"filename": name, "content": base64.b64encode(data).decode()}
                               for name, data in attachments]
    headers = {"Authorization": f"Bearer {key}"}
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key[:256]
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS, transport=transport) as client:
            resp = await client.post(RESEND_URL, json=body, headers=headers)
    except Exception as exc:
        return {"status": "failed", "id": None, "error": f"{type(exc).__name__}: {exc}"[:300]}
    if 200 <= resp.status_code < 300:
        try:
            email_id = resp.json().get("id")
        except Exception:
            email_id = None
        return {"status": "sent", "id": email_id, "error": None}
    return {"status": "failed", "id": None, "error": f"HTTP {resp.status_code}: {resp.text[:250]}"}
