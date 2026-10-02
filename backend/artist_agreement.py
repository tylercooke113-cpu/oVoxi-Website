"""Artist Agreement: versioned template, rendering, hashing, signed PDF and email.

Templates live in backend/agreements/<version>.txt and are never edited after
release. A new agreement is a new file and a new ARTIST_AGREEMENT_VERSION.

The hash covers the rendered agreement text with {{SIGNATURE_BLOCK}} left literal,
so the text shown at preview and the text signed can be compared exactly.
"""
import hashlib
import os
import re
from datetime import datetime
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

AGREEMENTS_DIR = Path(__file__).parent / "agreements"
SIGNATURE_MARKER = "{{SIGNATURE_BLOCK}}"
FIELDS = ("agreement_date", "licensor_party", "licensor_email", "platform_account_id")
LICENSEE_SIGNATORY = ("Tyler Jatzeck-Cooke", "Chief Executive Officer")

_PLACEHOLDER = re.compile(r"\{\{(\w+)\}\}")


def current_version() -> str:
    return os.environ.get("ARTIST_AGREEMENT_VERSION", "v1")


def enforced() -> bool:
    return os.environ.get("ARTIST_AGREEMENT_ENFORCED", "false") == "true"


@lru_cache(maxsize=8)
def load_template(version: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9._-]+", version):
        raise ValueError("Bad agreement version")
    return (AGREEMENTS_DIR / f"{version}.txt").read_text(encoding="utf-8")


def supports_buyouts(version: str) -> bool:
    """True when the agreement text contains the exclusive buyout clause (v2 and later)."""
    return "3.4 Exclusive Buyouts." in load_template(version)


def _ordinal(n: int) -> str:
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def agreement_date(now_utc: datetime) -> str:
    return f"{_ordinal(now_utc.day)} day of {now_utc.strftime('%B')}, {now_utc.year}"


def format_address(f: dict) -> str:
    region = " ".join(p for p in (f.get("region", ""), f.get("postal_code", "")) if p)
    parts = (f.get("address_line1"), f.get("address_line2"), f.get("city"), region, f.get("country"))
    return ", ".join(p for p in parts if p)


def licensor_party(f: dict) -> str:
    addr = format_address(f)
    if f["entity_type"] == "company":
        return f"{f['company_name']}, of {addr}"
    name = f["legal_name"]
    artist = (f.get("artist_name") or "").strip()
    if artist and artist.lower() != name.strip().lower():
        name = f'{name} p/k/a "{artist}"'
    return f"{name}, of {addr}"


def render_text(version: str, values: dict) -> str:
    def sub(m):
        key = m.group(1)
        if key == "SIGNATURE_BLOCK":
            return m.group(0)
        if key not in values:
            raise KeyError(f"Missing agreement value: {key}")
        return values[key]
    return _PLACEHOLDER.sub(sub, load_template(version))


def text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def blocks(text: str) -> list:
    """Structured paragraphs for the frontend. The frontend renders these as React
    elements; it never injects HTML."""
    out = []
    for para in (p.strip() for p in text.split("\n\n")):
        if not para:
            continue
        if para == SIGNATURE_MARKER:
            out.append({"type": "signature", "text": ""})
        elif para.startswith("# "):
            out.append({"type": "title", "text": para[2:]})
        elif para.startswith("## "):
            out.append({"type": "heading", "text": para[3:]})
        elif para.startswith("- "):
            out.append({"type": "item", "text": para[2:]})
        else:
            out.append({"type": "para", "text": para})
    return out


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------

INK = colors.HexColor("#111111")
MUTED = colors.HexColor("#666666")
PURPLE = colors.HexColor("#7B5EA7")
RULE = colors.HexColor("#DDDDDD")

_BASE = ParagraphStyle("ag_base", fontName="Times-Roman", fontSize=10.5, leading=14, textColor=INK, spaceAfter=6)
_TITLE = ParagraphStyle("ag_title", parent=_BASE, fontName="Times-Bold", fontSize=16, leading=20, alignment=1, spaceAfter=12)
_H2 = ParagraphStyle("ag_h2", parent=_BASE, fontName="Times-Bold", fontSize=11, spaceBefore=8, spaceAfter=4)
_ITEM = ParagraphStyle("ag_item", parent=_BASE, leftIndent=24)
_SIG = ParagraphStyle("ag_sig", parent=_BASE, fontName="Times-Italic", fontSize=15, leading=18, spaceAfter=2)
_SMALL = ParagraphStyle("ag_small", parent=_BASE, fontName="Helvetica", fontSize=8, leading=11, textColor=MUTED)


def _p(text, style=_BASE) -> Paragraph:
    return Paragraph(escape(str(text or "")), style)


def _footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(MUTED)
    canvas.drawString(0.8 * inch, 0.5 * inch, f"Agreement {doc.agreement_id}")
    canvas.drawRightString(LETTER[0] - 0.8 * inch, 0.5 * inch, f"Page {doc.page}")
    canvas.restoreState()


def _signature_flowables(sig: dict) -> list:
    f = sig["fields"]
    licensor = [_p("LICENSOR", _H2), _p(f"/s/ {sig['typed_signature']}", _SIG)]
    if f["entity_type"] == "company":
        licensor += [_p(f["company_name"]), _p(f"By: {f['legal_name']}, {f['signer_title']}")]
    else:
        licensor += [_p(f"Name: {f['legal_name']}")]
    licensor += [_p(f"Email: {sig['licensor_email']}"),
                 _p(f"Signed electronically on {sig['signed_at']} (UTC)", _SMALL)]
    name, title = LICENSEE_SIGNATORY
    licensee = [_p("LICENSEE", _H2), _p(f"/s/ {name}", _SIG), _p("OVOXI, Inc."),
                _p(f"By: {name}, {title}"), _p("Signed electronically", _SMALL)]
    table = Table([[licensor, licensee]], colWidths=[3.3 * inch, 3.3 * inch])
    table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                               ("LINEABOVE", (0, 0), (-1, 0), 0.5, RULE)]))
    return [Spacer(1, 6), table, Spacer(1, 10)]


def _audit_flowables(sig: dict) -> list:
    rows = [("Agreement ID", sig["agreement_id"]), ("Version", sig["version"]),
            ("Text SHA-256", sig["text_sha256"]), ("Signed at (UTC)", sig["signed_at"]),
            ("Platform account", sig["platform_account_id"]), ("IP address", sig["ip"]),
            ("Electronic signature consent", "Given"), ("Age confirmation", "18 or older")]
    table = Table([[_p(k, _SMALL), _p(v, _SMALL)] for k, v in rows], colWidths=[1.8 * inch, 4.8 * inch])
    table.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.25, RULE)]))
    return [Spacer(1, 16), _p("Signature record", _H2), table]


def render_pdf(text: str, sig: dict) -> bytes:
    """sig keys: agreement_id, version, text_sha256, signed_at, typed_signature,
    licensor_email, platform_account_id, ip, fields (AgreementFields as dict)."""
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=LETTER, leftMargin=0.9 * inch, rightMargin=0.9 * inch,
                            topMargin=0.9 * inch, bottomMargin=0.9 * inch,
                            title="oVoxi Artist Agreement", author="OVOXI, Inc.")
    doc.agreement_id = sig["agreement_id"]
    story = []
    for b in blocks(text):
        if b["type"] == "signature":
            story += _signature_flowables(sig)
        else:
            style = {"title": _TITLE, "heading": _H2, "item": _ITEM}.get(b["type"], _BASE)
            story.append(_p(b["text"], style))
    story += _audit_flowables(sig)

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------

def agreement_email(*, name: str, signed_date: str) -> tuple:
    subject = "Your signed oVoxi Artist Agreement"
    text = (f"Hi {name},\n\nThanks for signing the oVoxi Artist Agreement on {signed_date}. "
            "Your signed copy is attached. You can also download it any time from your Vault.\n\n"
            "Questions? Reply to this email.\n\noVoxi")
    html = (f"<p>Hi {escape(name)},</p><p>Thanks for signing the oVoxi Artist Agreement on "
            f"{escape(signed_date)}. Your signed copy is attached. You can also download it any "
            "time from your Vault.</p><p>Questions? Reply to this email.</p><p>oVoxi</p>")
    return subject, html, text
