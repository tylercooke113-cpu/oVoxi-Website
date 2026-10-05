"""License delivery email (PRD-03 7.2 step 5, 10). Content only; sending is email_sender.py.

The HTML template uses inline styles (email clients ignore <style>), so its lines run long.

Every value that came from a buyer or artist is HTML-escaped.
"""
# flake8: noqa: E501
from datetime import datetime
from html import escape

TIER_LABELS = {"creator": "Creator", "creator_pro": "Creator Pro", "business_social": "Business Social"}


def _fmt_date(iso: str | None) -> str:
    if not iso:
        return ""
    return datetime.fromisoformat(iso).strftime("%B %d, %Y")


def license_email(order: dict, *, download_url: str, reissued: bool = False) -> tuple[str, str, str]:
    """(subject, html, text) for a fulfilled order."""
    title = order.get("track_title") or "your track"
    artist = order.get("artist_display_name") or ""
    tier = TIER_LABELS.get(order.get("tier"), order.get("tier") or "")
    if order.get("include_stems"):
        tier += " + stems"
    lid = order.get("license_id", "")
    expires = _fmt_date(order.get("token_expires_at"))
    prefix = "[TEST] " if order.get("test_mode") else ""
    lead = "Here is a new download link for your license." if reissued else "Thanks for licensing on oVoxi."
    subject = f"{prefix}Your license for {title}" + (" (new download link)" if reissued else "")
    test_note = ("This is a test order. The files are for testing and the attached certificate "
                 "is not a valid license.") if order.get("test_mode") else ""

    text = "\n".join(line for line in [
        test_note,
        f"{lead}",
        "",
        f"Track: {title}" + (f" by {artist}" if artist else ""),
        f"Tier: {tier}",
        f"License ID: {lid}",
        "",
        f"Download your files: {download_url}",
        f"The link works until {expires}, with up to 10 downloads per file." if expires else "",
        "Your license certificate is attached. Keep it with your project files.",
        "",
        f"Questions? Reply to this email with your License ID ({lid}).",
        "oVoxi",
    ] if line is not None)

    e = escape
    html = f"""<!doctype html><html><body style="margin:0;background:#f4f4f5;font-family:Helvetica,Arial,sans-serif;color:#111">
<div style="max-width:560px;margin:0 auto;padding:24px">
<div style="height:6px;background:#7B5EA7;border-radius:3px 3px 0 0"></div>
<div style="background:#fff;padding:28px;border-radius:0 0 8px 8px">
{f'<p style="background:#fef3c7;color:#92400e;padding:10px 12px;border-radius:6px;font-size:13px;margin:0 0 16px">{e(test_note)}</p>' if test_note else ''}
<p style="font-size:15px;margin:0 0 16px">{e(lead)}</p>
<p style="font-size:20px;font-weight:bold;margin:0">{e(title)}</p>
<p style="color:#555;margin:4px 0 16px">{e(artist)}{' &middot; ' if artist else ''}{e(tier)}</p>
<p style="font-size:13px;color:#555;margin:0 0 20px">License ID <b>{e(lid)}</b></p>
<a href="{e(download_url, quote=True)}" style="display:inline-block;background:#7B5EA7;color:#fff;text-decoration:none;padding:12px 22px;border-radius:999px;font-size:14px">Download your files</a>
<p style="font-size:13px;color:#555;margin:16px 0 0">{('The link works until ' + e(expires) + ', with up to 10 downloads per file.') if expires else ''}</p>
<p style="font-size:13px;color:#555;margin:8px 0 0">Your license certificate is attached. Keep it with your project files.</p>
<p style="font-size:12px;color:#888;margin:24px 0 0">Questions? Reply to this email with your License ID.</p>
</div></div></body></html>"""
    return subject, html, text


def quote_email(q: dict) -> tuple[str, str, str]:
    """Internal notification for a licensing quote request (Brief 18). Details keep line breaks."""
    track = q.get("track_title") or "no track"
    subject = f"Licensing quote request: {q['kind']}, {track}"
    rows = [("Kind", q.get("kind")), ("Track", q.get("track_title") or "(none)"),
            ("Artist", q.get("artist_display_name") or "(none)"), ("Name", q.get("name")),
            ("Company", q.get("company") or "(none)"), ("Email", q.get("email")),
            ("Use", q.get("use")), ("Territory", q.get("territory") or "(none)"),
            ("Term", q.get("term") or "(none)"), ("Budget", q.get("budget"))]
    details = q.get("details") or ""
    html = "".join(f"<p style='margin:2px 0'><b>{escape(k)}:</b> {escape(str(v))}</p>" for k, v in rows)
    html += f"<p style='margin:10px 0 0'><b>Details:</b><br>{escape(details).replace(chr(10), '<br>')}</p>"
    text = "\n".join(f"{k}: {v}" for k, v in rows) + f"\n\nDetails:\n{details}"
    return subject, html, text
