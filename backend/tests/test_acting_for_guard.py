"""Brief 28 C2: the X-Acting-For allowlist and deny-by-default guard.

The route-enumeration test walks every api route and asserts the guard allows exactly the
Part 0 rows 1 to 10 and denies everything else. This catches any route the allowlist missed.
"""
import re
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.routing import APIRoute

import server


EXPECTED_ALLOWLIST = {
    ("POST", "/api/upload/presign"),
    ("POST", "/api/upload/complete"),
    ("GET", "/api/vault/tracks"),
    ("PATCH", "/api/vault/tracks/{track_id}/metadata"),
    ("POST", "/api/vault/tracks/{track_id}/declarations"),
    ("POST", "/api/vault/tracks/{track_id}/loops/{index}/license/presign"),
    ("POST", "/api/vault/tracks/{track_id}/loops/{index}/license/complete"),
    ("POST", "/api/vault/tracks/{track_id}/consent"),
    ("POST", "/api/vault/tracks/{track_id}/cosign/{request_id}/resend"),
    ("PATCH", "/api/vault/tracks/{track_id}/cosign/{request_id}"),
}


def _api_routes():
    """Every api route. Read from api_router directly: this FastAPI version wraps the routes
    in an _IncludedRouter on app.routes, but api_router.routes holds the APIRoutes with their
    full /api paths."""
    out = []
    for r in server.api_router.routes:
        if isinstance(r, APIRoute) and r.path.startswith("/api"):
            for m in (r.methods or set()):
                if m not in ("HEAD", "OPTIONS"):
                    out.append((m, r.path))
    return out


def test_allowlist_is_exactly_part0_rows():
    assert server.ACTING_FOR_ALLOWLIST == EXPECTED_ALLOWLIST


def test_allowlist_entries_are_all_real_routes():
    routes = set(_api_routes())
    for entry in server.ACTING_FOR_ALLOWLIST:
        assert entry in routes, f"allowlist entry {entry} is not a registered route"


def test_every_route_allowed_iff_in_allowlist():
    for method, template in _api_routes():
        concrete = re.sub(r"\{[^/]+\}", "x", template)
        allowed = server._acting_for_allowed(method, concrete)
        expected = (method, template) in server.ACTING_FOR_ALLOWLIST
        assert allowed == expected, f"{method} {template}: guard allowed={allowed}, expected={expected}"


def _req(method, path, acting=True):
    headers = {"x-acting-for": "artist_1"} if acting else {}
    return SimpleNamespace(method=method, url=SimpleNamespace(path=path), headers=headers)


def run(coro):
    import asyncio
    return asyncio.run(coro)


def test_guard_passes_when_no_header():
    # A non-allowlisted route is fine without the header (today's behavior).
    run(server.acting_for_guard(_req("GET", "/api/wallet/me", acting=False)))


def test_guard_allows_allowlisted_route_with_header():
    run(server.acting_for_guard(_req("POST", "/api/upload/presign")))
    run(server.acting_for_guard(_req("PATCH", "/api/vault/tracks/abc/metadata")))


def test_guard_denies_non_allowlisted_route_with_header():
    for method, path in [("GET", "/api/wallet/me"), ("GET", "/api/sync/profile"),
                         ("POST", "/api/agreement/sign"), ("GET", "/api/vault/uploaders"),
                         ("DELETE", "/api/vault/uploaders/abc")]:
        with pytest.raises(HTTPException) as e:
            run(server.acting_for_guard(_req(method, path)))
        assert e.value.status_code == 403
