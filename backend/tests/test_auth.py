"""
Unit tests for verify_clerk_token, _role, and require_role.

A local RSA keypair is generated once per session; _jwks_client is
monkeypatched so no network call is made in any test.
"""

import asyncio
import time
from unittest.mock import MagicMock

import jwt
import pytest
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException

import server


# ---------------------------------------------------------------------------
# Session-scoped keypair
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def private_key():
    return rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend(),
    )


@pytest.fixture(scope="session")
def private_key_pem(private_key):
    return private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )


@pytest.fixture(scope="session")
def public_key(private_key):
    return private_key.public_key()


@pytest.fixture(scope="session")
def public_key_pem(public_key):
    return public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )


# ---------------------------------------------------------------------------
# Autouse: patch _jwks_client for every test
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def patch_jwks(public_key, monkeypatch):
    signing_key = MagicMock()
    signing_key.key = public_key
    mock_client = MagicMock()
    mock_client.get_signing_key_from_jwt.return_value = signing_key
    monkeypatch.setattr(server, "_jwks_client", mock_client)
    return mock_client


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _token(private_key_pem, overrides=None, algorithm="RS256"):
    now = int(time.time())
    payload = {
        "sub": "user_test123",
        "iss": "https://clerk.test",
        "iat": now,
        "exp": now + 3600,
        "azp": "https://app.test",
    }
    if overrides:
        payload.update(overrides)
    if algorithm == "none":
        return jwt.encode(payload, "", algorithm="none")
    return jwt.encode(payload, private_key_pem, algorithm=algorithm)


def run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# verify_clerk_token
# ---------------------------------------------------------------------------

class TestVerifyClerkToken:
    def test_valid_token_returns_payload(self, private_key_pem):
        token = _token(private_key_pem)
        payload = run(server.verify_clerk_token(f"Bearer {token}"))
        assert payload["sub"] == "user_test123"

    def test_missing_header_is_401(self):
        with pytest.raises(HTTPException) as exc:
            run(server.verify_clerk_token(None))
        assert exc.value.status_code == 401
        assert exc.value.detail == "Not authenticated"

    def test_non_bearer_scheme_is_401(self):
        with pytest.raises(HTTPException) as exc:
            run(server.verify_clerk_token("Basic dXNlcjpwYXNz"))
        assert exc.value.status_code == 401

    def test_expired_token_is_401(self, private_key_pem):
        token = _token(private_key_pem, {"exp": int(time.time()) - 60})
        with pytest.raises(HTTPException) as exc:
            run(server.verify_clerk_token(f"Bearer {token}"))
        assert exc.value.status_code == 401
        assert exc.value.detail == "Not authenticated"

    def test_wrong_issuer_is_401(self, private_key_pem):
        token = _token(private_key_pem, {"iss": "https://evil.example.com"})
        with pytest.raises(HTTPException) as exc:
            run(server.verify_clerk_token(f"Bearer {token}"))
        assert exc.value.status_code == 401

    def test_azp_not_in_allowlist_is_401(self, private_key_pem):
        token = _token(private_key_pem, {"azp": "https://evil.example.com"})
        with pytest.raises(HTTPException) as exc:
            run(server.verify_clerk_token(f"Bearer {token}"))
        assert exc.value.status_code == 401

    def test_alg_none_is_401(self, private_key_pem):
        # jwt.encode with algorithm="none" produces a token with header alg=none.
        # jwt.decode with algorithms=["RS256"] rejects it — DecodeError is a
        # subclass of PyJWTError, which maps to 401.
        token = _token(private_key_pem, algorithm="none")
        with pytest.raises(HTTPException) as exc:
            run(server.verify_clerk_token(f"Bearer {token}"))
        assert exc.value.status_code == 401

    def test_401_detail_is_opaque(self, private_key_pem):
        # The reason a token failed must not be returned to the caller (finding #11).
        token = _token(private_key_pem, {"exp": int(time.time()) - 60})
        with pytest.raises(HTTPException) as exc:
            run(server.verify_clerk_token(f"Bearer {token}"))
        assert exc.value.detail == "Not authenticated"

    def test_clerk_outage_is_503(self, monkeypatch):
        outage_client = MagicMock()
        outage_client.get_signing_key_from_jwt.side_effect = (
            jwt.PyJWKClientConnectionError("connect timeout")
        )
        monkeypatch.setattr(server, "_jwks_client", outage_client)
        with pytest.raises(HTTPException) as exc:
            run(server.verify_clerk_token("Bearer anything"))
        assert exc.value.status_code == 503
        assert exc.value.detail == "Authentication temporarily unavailable"

    def test_algorithm_confusion_hs256_is_401(self, public_key_pem):
        # CVE-2024-33663 shape: token with alg=HS256 in the header, signed with
        # the RSA public key used as the HMAC secret.
        # PyJWT 2.14.0 refuses jwt.encode(HS256, PEM-key) at encode time, so the
        # token is constructed manually — exactly as an attacker would send it.
        # algorithms=["RS256"] must reject this at decode time regardless.
        import base64
        import hashlib
        import hmac as _hmac
        import json as _json

        def _b64url(data: bytes) -> str:
            return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

        now = int(time.time())
        hdr = _b64url(_json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
        body = _b64url(_json.dumps({
            "sub": "user_test123", "iss": "https://clerk.test",
            "iat": now, "exp": now + 3600, "azp": "https://app.test",
        }).encode())
        signing_input = f"{hdr}.{body}".encode()
        sig = _b64url(
            _hmac.new(public_key_pem, signing_input, hashlib.sha256).digest()
        )
        token = f"{hdr}.{body}.{sig}"

        with pytest.raises(HTTPException) as exc:
            run(server.verify_clerk_token(f"Bearer {token}"))
        assert exc.value.status_code == 401

    def test_lookalike_azp_is_401(self, private_key_pem, monkeypatch):
        # "https://ovoxi.net.evil.com" must not match an allowlist containing
        # "https://ovoxi.net" — set membership must be exact, not prefix/substring.
        monkeypatch.setattr(
            server, "CLERK_AUTHORIZED_PARTIES",
            {"https://ovoxi.net", "https://www.ovoxi.net"},
        )
        token = _token(private_key_pem, {"azp": "https://ovoxi.net.evil.com"})
        with pytest.raises(HTTPException) as exc:
            run(server.verify_clerk_token(f"Bearer {token}"))
        assert exc.value.status_code == 401


# ---------------------------------------------------------------------------
# require_role / require_admin / require_artist
# ---------------------------------------------------------------------------

class TestRequireRole:
    def test_require_admin_with_artist_role_is_403(self, private_key_pem):
        token = _token(private_key_pem, {"metadata": {"role": "artist"}})
        payload = run(server.verify_clerk_token(f"Bearer {token}"))
        with pytest.raises(HTTPException) as exc:
            run(server.require_admin(payload=payload))
        assert exc.value.status_code == 403

    def test_require_admin_with_no_role_is_403(self, private_key_pem):
        token = _token(private_key_pem)
        payload = run(server.verify_clerk_token(f"Bearer {token}"))
        with pytest.raises(HTTPException) as exc:
            run(server.require_admin(payload=payload))
        assert exc.value.status_code == 403

    def test_require_admin_with_admin_role_passes(self, private_key_pem):
        token = _token(private_key_pem, {"metadata": {"role": "admin"}})
        payload = run(server.verify_clerk_token(f"Bearer {token}"))
        result = run(server.require_admin(payload=payload))
        assert result["sub"] == "user_test123"

    def test_require_artist_with_artist_role_passes(self, private_key_pem):
        token = _token(private_key_pem, {"metadata": {"role": "artist"}})
        payload = run(server.verify_clerk_token(f"Bearer {token}"))
        result = run(server.require_artist(payload=payload))
        assert result["sub"] == "user_test123"

    def test_require_artist_with_admin_role_passes(self, private_key_pem):
        token = _token(private_key_pem, {"metadata": {"role": "admin"}})
        payload = run(server.verify_clerk_token(f"Bearer {token}"))
        result = run(server.require_artist(payload=payload))
        assert result["sub"] == "user_test123"
