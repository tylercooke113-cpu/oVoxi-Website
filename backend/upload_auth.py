"""Upload Authorization: versioned template, rendering, hashing, signed PDF and emails.

Modeled on cosign.py and deliberately reuses artist_agreement's primitives: the
template files share backend/agreements/, and render_text/text_sha256/blocks are
identical in behavior (placeholder substitution with {{SIGNATURE_BLOCK}} left
literal, so preview text and signed text compare exactly).

An Upload Authorization is a three-party agreement (Artist, Authorized Uploader,
Licensee). Where the Authorized Uploader is OVOXI itself, OVOXI is both the
Authorized Uploader and the Licensee, so the signature block collapses to two
parties (Artist and Licensee) -- see legal draft B and Decision 6.
"""
import os
from datetime import datetime
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Spacer, Table, TableStyle

import artist_agreement as aa

# Role labels the artist may choose for a named uploader, plus OVOXI for the Licensee case.
UPLOADER_ROLES = ("Engineer", "Studio owner", "Producer", "Manager", "OVOXI")

# The two kinds of Authorized Uploader (Decision 6) and the authorization lifecycle
# statuses (Brief 28 B1). "active" is the only status that grants acting rights.
AUTHORIZATION_KINDS = ("person", "ovoxi")
AUTHORIZATION_STATUSES = (
    "awaiting_uploader",   # person: artist signed, waiting for the uploader to sign
    "active",              # in effect
    "revoked",             # artist revoked
    "ended_by_uploader",   # uploader ended
    "ended_agreement",     # ended because the Artist Agreement ended (2.3(d)/7.2)
    "declined",            # uploader declined the invitation
    "expired",             # signing link expired before the uploader signed
)

# uploader_party line when the Authorized Uploader is OVOXI itself (legal draft B note).
OVOXI_UPLOADER_PARTY = "OVOXI, Inc., acting through its employees"


def current_version() -> str:
    return os.environ.get("UPLOAD_AUTH_VERSION", "upload_auth_v1")


def authorized_uses_text(uses: list) -> str:
    """The {{authorized_uses}} phrase, from the artist's checkboxes. At least one use is
    required."""
    s = set(uses or [])
    if "ai_training" in s and "sync" in s:
        return "the AI Training Field of Use and the Sync Field of Use"
    if "sync" in s:
        return "the Sync Field of Use only"
    if "ai_training" in s:
        return "the AI Training Field of Use only"
    raise ValueError("At least one authorized use is required")


def uploader_party(kind: str, uploader_name: str = "") -> str:
    """The Authorized Uploader party line. For OVOXI, a fixed phrase; otherwise the
    person's or company's name as the artist entered it."""
    if kind == "ovoxi":
        return OVOXI_UPLOADER_PARTY
    return (uploader_name or "").strip()


def build_values(*, now: datetime, licensor_party: str, licensor_email: str,
                 platform_account_id: str, kind: str, uploader_name: str,
                 uploader_email: str, uploader_role: str, uses: list) -> dict:
    """All placeholder values for the upload_auth template. The renderer substitutes only
    the placeholders a template actually contains and ignores any extra value."""
    return {
        "authorization_date": aa.agreement_date(now),
        "licensor_party": licensor_party,
        "licensor_email": licensor_email,
        "platform_account_id": platform_account_id,
        "uploader_party": uploader_party(kind, uploader_name),
        "uploader_email": uploader_email,
        "uploader_role": uploader_role,
        "authorized_uses": authorized_uses_text(uses),
    }


def render_text(values: dict, version: str = None) -> str:
    return aa.render_text(version or current_version(), values)


def text_sha256(text: str) -> str:
    return aa.text_sha256(text)


def blocks(text: str) -> list:
    return aa.blocks(text)


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------

def _signature_flowables(sig: dict) -> list:
    """Artist | Authorized Uploader | Licensee. When the uploader is OVOXI
    (kind == "ovoxi"), OVOXI is both Authorized Uploader and Licensee, so only the
    Artist and Licensee columns are shown (Decision 6, legal draft B note)."""
    artist = [aa._p("ARTIST", aa._H2), aa._p(f"/s/ {sig['artist_typed_signature']}", aa._SIG),
              aa._p(f"Name: {sig['artist_legal_name']}"),
              aa._p(f"Email: {sig['artist_email']}"),
              aa._p(f"Signed electronically on {sig['artist_signed_at']} (UTC)", aa._SMALL)]
    name, title = aa.LICENSEE_SIGNATORY
    licensee = [aa._p("LICENSEE", aa._H2), aa._p(f"/s/ {name}", aa._SIG), aa._p("OVOXI, Inc."),
                aa._p(f"By: {name}, {title}"), aa._p("Signed electronically", aa._SMALL)]
    if sig.get("kind") == "ovoxi":
        cells, widths = [artist, licensee], [3.3 * inch, 3.3 * inch]
    else:
        uploader = [aa._p("AUTHORIZED UPLOADER", aa._H2),
                    aa._p(f"/s/ {sig['uploader_typed_signature']}", aa._SIG),
                    aa._p(f"Name: {sig['uploader_name']}"),
                    aa._p(f"Email: {sig['uploader_email']}"),
                    aa._p(f"Signed electronically on {sig['uploader_signed_at']} (UTC)", aa._SMALL)]
        cells, widths = [artist, uploader, licensee], [2.2 * inch, 2.2 * inch, 2.2 * inch]
    table = Table([cells], colWidths=widths)
    table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                               ("LINEABOVE", (0, 0), (-1, 0), 0.5, aa.RULE)]))
    return [Spacer(1, 6), table, Spacer(1, 10)]


def _audit_flowables(sig: dict) -> list:
    rows = [("Authorization ID", sig["authorization_id"]),
            ("Document fingerprint", sig["text_sha256"][:16]),
            ("Text SHA-256", sig["text_sha256"]),
            ("Artist signed at (UTC)", sig["artist_signed_at"]),
            ("Artist IP address", sig["artist_ip"])]
    if sig.get("kind") != "ovoxi":
        rows += [("Uploader signed at (UTC)", sig["uploader_signed_at"]),
                 ("Uploader email", sig["uploader_email"]),
                 ("Uploader IP address", sig["uploader_ip"])]
    rows += [("Electronic signature consent", "Given"), ("Age confirmation", "18 or older")]
    table = Table([[aa._p(k, aa._SMALL), aa._p(v, aa._SMALL)] for k, v in rows],
                  colWidths=[1.8 * inch, 4.8 * inch])
    table.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.25, aa.RULE)]))
    return [Spacer(1, 16), aa._p("Signature record", aa._H2), table]


def render_pdf(text: str, sig: dict) -> bytes:
    """sig keys: authorization_id, version, text_sha256, kind ("person" or "ovoxi"),
    artist_typed_signature, artist_legal_name, artist_email, artist_signed_at, artist_ip,
    and, when kind != "ovoxi": uploader_typed_signature, uploader_name, uploader_email,
    uploader_signed_at, uploader_ip."""
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=LETTER, leftMargin=0.9 * inch, rightMargin=0.9 * inch,
                            topMargin=0.9 * inch, bottomMargin=0.9 * inch,
                            title="OVOXI Upload Authorization", author="OVOXI, Inc.")
    doc.agreement_id = sig["authorization_id"]
    story = []
    for b in blocks(text):
        if b["type"] == "signature":
            story += _signature_flowables(sig)
        else:
            style = {"title": aa._TITLE, "heading": aa._H2, "item": aa._ITEM}.get(b["type"], aa._BASE)
            story.append(aa._p(b["text"], style))
    story += _audit_flowables(sig)
    doc.build(story, onFirstPage=aa._footer, onLaterPages=aa._footer)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------

def invitation_email(*, artist_name: str, uploader_role: str, uses: list, link: str) -> tuple:
    """Invitation to the named uploader to review and sign (Part C7). Plain and short."""
    uses_line = authorized_uses_text(uses)
    subject = f"{artist_name} invited you to upload on OVOXI"
    text = (
        f"{artist_name} added you as an Authorized Uploader on OVOXI, acting as {uploader_role}.\n\n"
        f"You can upload songs to {artist_name}'s account and set these uses: {uses_line}.\n\n"
        "Only the artist can take songs down, turn on Exclusive or see the Wallet.\n\n"
        f"Review and sign: {link}\n\n"
        "This link expires in 30 days.\n\n"
        "If you did not expect this, you can ignore this email or decline on the page.\n\nOVOXI"
    )
    html = (
        f"<p>{escape(artist_name)} added you as an Authorized Uploader on OVOXI, acting as "
        f"{escape(uploader_role)}.</p>"
        f"<p>You can upload songs to {escape(artist_name)}'s account and set these uses: "
        f"{escape(uses_line)}.</p>"
        "<p>Only the artist can take songs down, turn on Exclusive or see the Wallet.</p>"
        f'<p><a href="{escape(link, {chr(34): "&quot;"})}" style="display:inline-block;'
        "background:#7B5EA7;color:#fff;text-decoration:none;padding:12px 22px;border-radius:999px;"
        'font-size:14px">Review and sign</a></p>'
        "<p>This link expires in 30 days.</p>"
        "<p>If you did not expect this, you can ignore this email or decline on the page.</p><p>OVOXI</p>"
    )
    return subject, html, text


def signed_copy_email(*, artist_name: str) -> tuple:
    """Signed copy sent to the artist, the uploader and tyler@ovoxi.net (Part C1)."""
    subject = "Your signed OVOXI Upload Authorization"
    text = (f"The OVOXI Upload Authorization for {artist_name}'s account is now signed. "
            "A copy is attached.\n\nQuestions? Reply to this email.\n\nOVOXI")
    html = (f"<p>The OVOXI Upload Authorization for {escape(artist_name)}'s account is now signed. "
            "A copy is attached.</p><p>Questions? Reply to this email.</p><p>OVOXI</p>")
    return subject, html, text


def digest_email(*, items: list, link: str) -> tuple:
    """Daily digest to the artist (Upload Authorization 6.1): the songs an uploader added
    today. items: [{title, uploader, uses}]. uses is a list of "ai_training"/"sync"."""
    def _uses(us):
        names = {"ai_training": "AI training", "sync": "sync"}
        return " and ".join(names[u] for u in us) if us else "no uses yet"
    n = len(items)
    subject = f"{n} song{'s' if n != 1 else ''} added to your OVOXI account today"
    lines = [f"- \"{it['title']}\" by {it['uploader']} ({_uses(it.get('uses'))})" for it in items]
    text = ("An uploader added these songs to your OVOXI account today:\n\n"
            + "\n".join(lines) + f"\n\nReview them in your Vault: {link}\n\nOVOXI")
    rows = "".join(
        f"<li>&quot;{escape(it['title'])}&quot; by {escape(it['uploader'])} "
        f"({escape(_uses(it.get('uses')))})</li>" for it in items)
    html = ("<p>An uploader added these songs to your OVOXI account today:</p>"
            f"<ul>{rows}</ul>"
            f'<p><a href="{escape(link, {chr(34): "&quot;"})}">Review them in your Vault</a></p>'
            "<p>OVOXI</p>")
    return subject, html, text


def revocation_email(*, artist_name: str) -> tuple:
    """Sent to the uploader when the artist revokes the authorization (Part C1)."""
    subject = f"{artist_name} ended your OVOXI upload access"
    text = (f"{artist_name} has revoked your Upload Authorization on OVOXI. You can no longer "
            "upload or make changes for that account. Songs already uploaded are not affected.\n\n"
            "Questions? Reply to this email.\n\nOVOXI")
    html = (f"<p>{escape(artist_name)} has revoked your Upload Authorization on OVOXI. You can no "
            "longer upload or make changes for that account. Songs already uploaded are not "
            "affected.</p><p>Questions? Reply to this email.</p><p>OVOXI</p>")
    return subject, html, text


def ended_email(*, artist_name: str, uploader_name: str) -> tuple:
    """Sent to the artist when the uploader ends the authorization (Part C1)."""
    subject = f"{uploader_name} ended their OVOXI upload access for your account"
    text = (f"{uploader_name} has ended their Upload Authorization for your OVOXI account. They can "
            "no longer upload or make changes for you. Songs already uploaded are not affected.\n\n"
            "Questions? Reply to this email.\n\nOVOXI")
    html = (f"<p>{escape(uploader_name)} has ended their Upload Authorization for your OVOXI account. "
            "They can no longer upload or make changes for you. Songs already uploaded are not "
            "affected.</p><p>Questions? Reply to this email.</p><p>OVOXI</p>")
    return subject, html, text
