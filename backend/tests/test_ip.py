"""Unit tests for get_real_client_ip."""
from unittest.mock import MagicMock
import server


def _req(headers: dict, client_host="10.0.0.1"):
    req = MagicMock()
    store = {k.lower(): v for k, v in headers.items()}
    req.headers.get.side_effect = lambda key, default="": store.get(key.lower(), default)
    if client_host is not None:
        req.client = MagicMock()
        req.client.host = client_host
    else:
        req.client = None
    return req


class TestGetRealClientIp:
    def test_prefers_x_real_ip(self):
        req = _req({"x-real-ip": "1.2.3.4", "x-forwarded-for": "5.6.7.8, 9.10.11.12"})
        assert server.get_real_client_ip(req) == "1.2.3.4"

    def test_falls_back_to_leftmost_x_forwarded_for(self):
        req = _req({"x-forwarded-for": "1.2.3.4, 5.6.7.8, 9.10.11.12"})
        assert server.get_real_client_ip(req) == "1.2.3.4"

    def test_falls_back_to_client_host_when_both_absent(self):
        req = _req({}, client_host="10.0.0.1")
        assert server.get_real_client_ip(req) == "10.0.0.1"

    def test_whitespace_x_real_ip_falls_through_to_forwarded_for(self):
        req = _req({"x-real-ip": "   ", "x-forwarded-for": "1.2.3.4, 5.6.7.8"})
        assert server.get_real_client_ip(req) == "1.2.3.4"

    def test_whitespace_forwarded_for_falls_through_to_client_host(self):
        req = _req({"x-forwarded-for": "   "}, client_host="10.0.0.1")
        assert server.get_real_client_ip(req) == "10.0.0.1"

    def test_no_client_returns_unknown(self):
        req = _req({}, client_host=None)
        assert server.get_real_client_ip(req) == "unknown"
