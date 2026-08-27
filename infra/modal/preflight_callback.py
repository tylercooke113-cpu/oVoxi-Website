"""
Pre-flight verification for the /04 stem callback contract.

Runs INSIDE Modal so it uses the exact `ovoxi-stem-secrets` values the real worker
will use -- not values retyped by hand.

    modal run infra/modal/preflight_callback.py

It sends ONE signed request with status "ping". The server verifies the HMAC first
and only then looks at the payload, so:

    400  -> signature VALID. Secret matches. Nothing was written to the database.
    401  -> signature INVALID. STEM_WEBHOOK_SECRET differs between Modal and Railway.
    500  -> STEM_WEBHOOK_SECRET is not set on Railway.
    200  -> DANGER: the real callback route never returns 200 for status "ping".
            You are almost certainly still pointed at webhook.site or another
            catch-all endpoint. Check the URL printed above the result.

No submission document is touched: "preflight-ping" matches no record, and the
"ping" status is rejected before any write path is reached.
"""

import hashlib
import hmac
import json
import os

import modal

app = modal.App("ovoxi-preflight")

image = modal.Image.debian_slim(python_version="3.12").pip_install("requests")

EXPECTED_HOST = "ovoxi-website-production.up.railway.app"
EXPECTED_PATH = "/api/internal/stems/callback"


@app.function(
    image=image,
    timeout=60,
    secrets=[modal.Secret.from_name("ovoxi-stem-secrets")],
)
def ping() -> None:
    import requests
    from urllib.parse import urlparse

    url = os.environ.get("STEM_CALLBACK_URL", "")
    secret = os.environ.get("STEM_WEBHOOK_SECRET", "")

    print("=" * 68)
    if not url:
        print("FAIL  STEM_CALLBACK_URL is not set in ovoxi-stem-secrets.")
        return
    if not secret:
        print("FAIL  STEM_WEBHOOK_SECRET is not set in ovoxi-stem-secrets.")
        return

    parsed = urlparse(url)
    print(f"STEM_CALLBACK_URL : {url}")

    if parsed.netloc != EXPECTED_HOST:
        print(f"  !! HOST MISMATCH -- expected {EXPECTED_HOST}")
        print("  !! This is the webhook.site failure mode. Fix before going further.")
    if parsed.path != EXPECTED_PATH:
        print(f"  !! PATH MISMATCH -- expected {EXPECTED_PATH}")

    # Fingerprint only. The secret itself is never printed.
    fp = hashlib.sha256(secret.encode()).hexdigest()[:12]
    print(f"secret fingerprint: {fp}   (length {len(secret)})")
    print("  Compare this against Railway's value if the result below is 401.")
    print("-" * 68)

    # Serialized EXACTLY as stem_worker._post_callback does. Any deviation here
    # would make this test meaningless.
    payload = {"submission_id": "preflight-ping", "status": "ping"}
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    try:
        resp = requests.post(
            url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "X-Ovoxi-Signature": f"sha256={sig}",
            },
            timeout=30,
        )
    except Exception as exc:
        print(f"FAIL  Request never completed: {exc}")
        print("      The callback URL is unreachable from Modal.")
        return

    print(f"HTTP {resp.status_code}")
    print(f"body: {resp.text[:300]}")
    print("-" * 68)

    if resp.status_code == 400:
        print("PASS  Signature accepted. Modal and Railway share the same secret.")
        print("      Nothing was written. Step 2 is verified.")
    elif resp.status_code == 401:
        print("FAIL  Signature rejected. STEM_WEBHOOK_SECRET differs between")
        print("      Modal and Railway. Re-set both from one generated value.")
    elif resp.status_code == 500:
        print("FAIL  Railway has no STEM_WEBHOOK_SECRET configured.")
    elif resp.status_code == 200:
        print("FAIL  A 200 here means you are NOT talking to the real callback")
        print("      route. Check the URL printed above.")
    else:
        print("UNEXPECTED  Investigate before proceeding.")
    print("=" * 68)


@app.local_entrypoint()
def main() -> None:
    ping.remote()
