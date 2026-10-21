"""Co-owner Consent: versioned template, rendering, hashing, signed PDF and email.

Modeled on artist_agreement.py and deliberately reuses its primitives: the
template files share backend/agreements/, and render_text/text_sha256/blocks are
identical in behavior (placeholder substitution with {{SIGNATURE_BLOCK}} left
literal, so preview text and signed text compare exactly).

A Co-owner Consent is a short, one-song document. It incorporates the Artist
Agreement the uploader signed; its text is shown to the co-owner alongside this
Consent but is not re-signed here.
"""
import os
from datetime import datetime
from io import BytesIO

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

import artist_agreement as aa
from sync_constants import PUBLISHER_ROLE_LABELS, WRITER_ROLE_LABELS

SIDE_LABELS = {"writers": "Writer", "publishers": "Publisher", "master_owners": "Master owner"}
ROLE_LABELS = {"writers": WRITER_ROLE_LABELS, "publishers": PUBLISHER_ROLE_LABELS, "master_owners": {}}


def current_version() -> str:
    return os.environ.get("COSIGN_VERSION", "cosign_v1")


def _pct(share_bp: int) -> str:
    return f"{share_bp / 100:.2f}".rstrip("0").rstrip(".")


def coowner_party(entity_type: str, legal_name: str,
                  signer_name: str = "", signer_title: str = "") -> str:
    """The Co-owner party line. For companies: "{company}, by {name}, {title}"."""
    legal_name = (legal_name or "").strip()
    if entity_type == "company":
        return f"{legal_name}, by {(signer_name or '').strip()}, {(signer_title or '').strip()}"
    return legal_name


def format_interests(interests: list) -> str:
    """One line per interest: "Writer (Composer & lyricist), 50%"."""
    lines = []
    for it in interests:
        side = it.get("side")
        label = SIDE_LABELS.get(side, side)
        role_label = ROLE_LABELS.get(side, {}).get(it.get("role"))
        head = f"{label} ({role_label})" if role_label else label
        lines.append(f"{head}, {_pct(it.get('share_bp', 0))}%")
    return "\n".join(lines)


def build_values(*, now: datetime, entity_type: str, legal_name: str, coowner_email: str,
                 uploader_name: str, artist_agreement_version: str,
                 work_title: str, work_artist: str, work_id: str, interests: list,
                 signer_name: str = "", signer_title: str = "") -> dict:
    """All placeholder values for cosign_v1.txt. The co-owner's typed legal name goes
    into coowner_party, so the hash changes when the name or entity fields change: the
    page must re-fetch the rendered text (preview) before signing."""
    return {
        "consent_date": aa.agreement_date(now),
        "coowner_party": coowner_party(entity_type, legal_name, signer_name, signer_title),
        "coowner_email": coowner_email,
        "uploader_name": uploader_name,
        "artist_agreement_version": artist_agreement_version,
        "work_title": work_title,
        "work_artist": work_artist,
        "work_id": work_id,
        "interests": format_interests(interests),
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
    """Co-owner on the left, Licensee (fixed) on the right. Mirrors the agreement's
    layout, reading the co-owner side instead of the licensor side."""
    coowner = [aa._p("CO-OWNER", aa._H2), aa._p(f"/s/ {sig['typed_signature']}", aa._SIG)]
    if sig["entity_type"] == "company":
        coowner += [aa._p(sig["legal_name"]),
                    aa._p(f"By: {sig['signer_name']}, {sig['signer_title']}")]
    else:
        coowner += [aa._p(f"Name: {sig['legal_name']}")]
    coowner += [aa._p(f"Email: {sig['coowner_email']}"),
                aa._p(f"Signed electronically on {sig['signed_at']} (UTC)", aa._SMALL)]
    name, title = aa.LICENSEE_SIGNATORY
    licensee = [aa._p("LICENSEE", aa._H2), aa._p(f"/s/ {name}", aa._SIG), aa._p("OVOXI, Inc."),
                aa._p(f"By: {name}, {title}"), aa._p("Signed electronically", aa._SMALL)]
    table = Table([[coowner, licensee]], colWidths=[3.3 * inch, 3.3 * inch])
    table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                               ("LINEABOVE", (0, 0), (-1, 0), 0.5, aa.RULE)]))
    return [Spacer(1, 6), table, Spacer(1, 10)]


def _audit_flowables(sig: dict) -> list:
    rows = [("Consent ID", sig["request_id"]), ("Version", sig["version"]),
            ("Work ID", sig["work_id"]), ("Text SHA-256", sig["text_sha256"]),
            ("Signed at (UTC)", sig["signed_at"]), ("Co-owner email", sig["coowner_email"]),
            ("IP address", sig["ip"]), ("Electronic signature consent", "Given"),
            ("Age confirmation", "18 or older")]
    table = Table([[aa._p(k, aa._SMALL), aa._p(v, aa._SMALL)] for k, v in rows],
                  colWidths=[1.8 * inch, 4.8 * inch])
    table.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.25, aa.RULE)]))
    return [Spacer(1, 16), aa._p("Signature record", aa._H2), table]


def render_pdf(text: str, sig: dict) -> bytes:
    """sig keys: request_id, version, work_id, text_sha256, signed_at, typed_signature,
    entity_type, legal_name, signer_name, signer_title, coowner_email, ip."""
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=LETTER, leftMargin=0.9 * inch, rightMargin=0.9 * inch,
                            topMargin=0.9 * inch, bottomMargin=0.9 * inch,
                            title="OVOXI Co-owner Consent", author="OVOXI, Inc.")
    doc.agreement_id = sig["request_id"]
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

def request_email(*, uploader_name: str, work_title: str, interests: list, uses: list,
                  link: str) -> tuple:
    """Invitation to review and sign. Plain and short (brief C3)."""
    from xml.sax.saxutils import escape
    subject = f'{uploader_name} listed you as a rights holder on "{work_title}"'
    uses_line = " and ".join(uses) if uses else "AI training and sync"
    interest_lines = format_interests(interests)
    text = (
        f"{uploader_name} uploaded \"{work_title}\" to OVOXI and listed you as a rights holder.\n\n"
        f"Your interest in the song:\n{interest_lines}\n\n"
        "OVOXI licenses songs for AI training and sync only when every rights holder agrees. "
        f"This song is opted into: {uses_line}.\n\n"
        f"Review and sign: {link}\n\n"
        "This link expires in 30 days.\n\n"
        "If you don't know this song, you can ignore this email or decline on the page.\n\nOVOXI"
    )
    rows = "".join(f"<li>{escape(l)}</li>" for l in interest_lines.split("\n") if l)
    html = (
        f"<p>{escape(uploader_name)} uploaded &quot;{escape(work_title)}&quot; to OVOXI and listed "
        "you as a rights holder.</p>"
        f"<p>Your interest in the song:</p><ul>{rows}</ul>"
        "<p>OVOXI licenses songs for AI training and sync only when every rights holder agrees. "
        f"This song is opted into: {escape(uses_line)}.</p>"
        f'<p><a href="{escape(link, {chr(34): "&quot;"})}" style="display:inline-block;'
        "background:#7B5EA7;color:#fff;text-decoration:none;padding:12px 22px;border-radius:999px;"
        'font-size:14px">Review and sign</a></p>'
        "<p>This link expires in 30 days.</p>"
        "<p>If you don't know this song, you can ignore this email or decline on the page.</p><p>OVOXI</p>"
    )
    return subject, html, text


def signed_copy_email(*, work_title: str) -> tuple:
    subject = f'Your signed OVOXI Co-owner Consent for "{work_title}"'
    text = (f'Thanks for signing the OVOXI Co-owner Consent for "{work_title}". '
            "Your signed copy is attached.\n\nQuestions? Reply to this email.\n\nOVOXI")
    from xml.sax.saxutils import escape
    html = (f'<p>Thanks for signing the OVOXI Co-owner Consent for &quot;{escape(work_title)}&quot;. '
            "Your signed copy is attached.</p><p>Questions? Reply to this email.</p><p>OVOXI</p>")
    return subject, html, text
