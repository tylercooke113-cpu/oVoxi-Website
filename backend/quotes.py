"""Licensing quote requests (Brief 18). Stored in quote_requests; emailed to QUOTE_INBOX.

Pure helpers: no DB or email. The server route does the storing, emailing and rate limiting.
"""
import os
import re
import uuid
from datetime import datetime

USES = ("Exclusive buyout", "National TV campaign", "Feature film", "Game", "Other")
BUDGETS = ("Under $5,000", "$5,000 to $25,000", "$25,000 to $100,000", "Over $100,000")

# Inline fields reject all control characters and braces. Details keep newlines (see clean_multiline).
_BAD_INLINE = re.compile(r"[\x00-\x1f\x7f]|\{\{|\}\}")
_BAD_MULTILINE = re.compile(r"[\x00-\x09\x0b-\x1f\x7f]|\{\{|\}\}")  # every control except newline (\x0a)


def quote_inbox() -> str:
    return os.environ.get("QUOTE_INBOX", "").strip() or "tyler@ovoxi.net"


def clean(v: str, limit: int = 120) -> str:
    v = " ".join((v or "").split())
    if _BAD_INLINE.search(v):
        raise ValueError("Remove special characters from this field.")
    return v[:limit]


def clean_multiline(v: str, limit: int = 2000) -> str:
    """Keep line breaks: reject controls other than newline, trim each line, collapse 3+ newlines to one."""
    v = v or ""
    if _BAD_MULTILINE.search(v):
        raise ValueError("Remove special characters from this field.")
    text = "\n".join(line.strip() for line in v.split("\n"))
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()[:limit]


def build_quote(payload: dict, *, ip: str, user_agent: str, track: dict | None, now: datetime) -> dict:
    return {
        "id": uuid.uuid4().hex, "created_at": now.isoformat(), "ip": ip, "user_agent": (user_agent or "")[:300],
        "kind": payload["kind"], "track_id": payload.get("track_id"),
        "track_title": (track or {}).get("track_name"),
        "artist_display_name": (track or {}).get("artist_name"),
        "name": payload["name"], "company": payload.get("company") or "", "email": payload["email"],
        "use": payload["use"], "territory": payload.get("territory") or "", "term": payload.get("term") or "",
        "budget": payload["budget"], "details": payload.get("details") or "",
    }
