"""License PDF for a sync order (PRD-03 7.4). ReportLab, built-in Helvetica only (no font files).

User-supplied text (buyer name, company, track and artist names) is escaped before it
reaches ReportLab's Paragraph markup parser. Test-mode orders carry a watermark so a
sandbox PDF can never be mistaken for a real license.
"""
from datetime import datetime
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing

PURPLE = colors.HexColor("#7B5EA7")
INK = colors.HexColor("#111111")
MUTED = colors.HexColor("#666666")
RULE = colors.HexColor("#DDDDDD")

# Keyed by terms_version. Each value is a list of blocks {"type", "text"}; the file-backed
# v1 terms and the kept draft-0 both render through the same block loop.
TERMS_DIR = Path(__file__).parent / "terms"


def _parse_terms(text: str) -> list:
    blocks = []
    for para in text.split("\n\n"):
        p = para.strip()
        if not p:
            continue
        if p.startswith("## "):
            blocks.append({"type": "heading", "text": p[3:]})
        elif p.startswith("# "):
            blocks.append({"type": "title", "text": p[2:]})
        elif p.startswith("- "):
            blocks.append({"type": "item", "text": p[2:]})
        else:
            blocks.append({"type": "para", "text": p})
    return blocks


_DRAFT0 = [{"type": "para", "text": t} for t in (
    "PLACEHOLDER TERMS. This text is a draft pending legal review and is not the final license.",
    "1. Grant. oVoxi grants the Licensee a non-exclusive, non-transferable license to synchronize "
    "the Track with the Licensee's audiovisual content within the scope of the Tier named above.",
    "2. Restrictions. The Licensee may not resell, sublicense or redistribute the Track or its stems "
    "as standalone audio, register the Track with any content identification system, or use the Track "
    "to train, fine-tune or evaluate any machine learning model.",
    "3. Term. The license is perpetual for content published during the license period, subject to "
    "the Tier's scope.",
    "4. Refunds. If the purchase is refunded, this license is void from the refund date.",
)]

TERMS = {
    "draft-0": _DRAFT0,
    "v1": _parse_terms((TERMS_DIR / "license_v1.txt").read_text(encoding="utf-8")),
}

_BASE = ParagraphStyle("base", fontName="Helvetica", fontSize=10, leading=14, textColor=INK, alignment=TA_LEFT)
_TITLE = ParagraphStyle("title", parent=_BASE, fontName="Helvetica-Bold", fontSize=20, leading=24)
_SUB = ParagraphStyle("sub", parent=_BASE, textColor=MUTED)
_H2 = ParagraphStyle("h2", parent=_BASE, fontName="Helvetica-Bold", fontSize=11, spaceBefore=6, spaceAfter=4)
_LABEL = ParagraphStyle("label", parent=_BASE, textColor=MUTED, fontSize=9)
_SMALL = ParagraphStyle("small", parent=_BASE, fontSize=8.5, leading=12, textColor=MUTED)
_ITEM = ParagraphStyle("item", parent=_BASE, leftIndent=14)

TIER_LABELS = {"creator": "Creator", "creator_pro": "Creator Pro", "business_social": "Business Social"}


def _money(cents, currency: str) -> str:
    if cents is None:
        return "n/a"
    return f"${cents / 100:,.2f} {currency.upper()}"


def _p(text, style=_BASE) -> Paragraph:
    return Paragraph(escape(str(text or "")), style)


def _qr(url: str, size: float = 72.0) -> Drawing:
    """About a 1 inch QR of the verification URL."""
    widget = QrCodeWidget(url)
    x0, y0, x1, y1 = widget.getBounds()
    d = Drawing(size, size, transform=[size / (x1 - x0), 0, 0, size / (y1 - y0), 0, 0])
    d.add(widget)
    return d


def _watermark(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica-Bold", 44)
    canvas.setFillColor(colors.Color(0.85, 0.1, 0.1, alpha=0.18))
    canvas.translate(LETTER[0] / 2, LETTER[1] / 2)
    canvas.rotate(35)
    canvas.drawCentredString(0, 0, "TEST ORDER")
    canvas.setFont("Helvetica-Bold", 18)
    canvas.drawCentredString(0, -30, "NOT A VALID LICENSE")
    canvas.restoreState()


def _header_bar(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(PURPLE)
    canvas.rect(0, LETTER[1] - 0.18 * inch, LETTER[0], 0.18 * inch, stroke=0, fill=1)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(MUTED)
    canvas.drawString(0.8 * inch, 0.5 * inch, "oVoxi  |  ovoxi.net")
    canvas.drawRightString(LETTER[0] - 0.8 * inch, 0.5 * inch, f"Page {doc.page}")
    canvas.restoreState()


def render_license_pdf(order: dict, *, track_title: str, artist_name: str,
                       license: dict = None, verify_url: str = None) -> bytes:
    """PDF bytes for a paid order. Raises KeyError if the order's terms_version has no text."""
    terms = TERMS[order["terms_version"]]
    issued = datetime.fromisoformat(order.get("paid_at") or order["created_at"]).strftime("%B %d, %Y")
    currency = order.get("currency", "usd")
    lic = license or {}
    scope = lic.get("scope") or {}
    project = lic.get("project") or {}
    is_sub = lic.get("source") == "subscription"

    rows = [
        ("License ID", order["license_id"]),
        ("Date issued", issued),
        ("Licensee", order["buyer_name"]),
        ("Company", order.get("buyer_company") or "None"),
        ("Email", order["buyer_email"]),
        ("Track", track_title),
        ("Artist", artist_name),
        (("Plan", lic.get("license_label")) if is_sub
         else ("Tier", TIER_LABELS.get(order["tier"], order["tier"]))),
        *([("Project", project.get("name"))] if project.get("name") else []),
        *([("Client", project.get("client"))] if project.get("client") else []),
        *([("Territory", scope.get("territory"))] if scope.get("territory") else []),
        *([("Term", scope.get("term_label"))] if scope.get("term_label") else []),
        *([("Paid media", _money(scope.get("media_spend_cap_cents"), currency))]
          if scope.get("media_spend_cap_cents") else []),
        ("Stems included", "Yes" if order.get("include_stems") else "No"),
        *([] if is_sub else [
            ("License fee", _money(order.get("price_cents"), currency)),
            ("Tax", _money(order.get("tax_cents"), currency)),
            ("Total paid", _money(order.get("amount_total_cents"), currency))]),
        ("Terms version", order["terms_version"]),
    ]
    table = Table([[_p(k, _LABEL), _p(v)] for k, v in rows], colWidths=[1.7 * inch, 5.0 * inch])
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, RULE),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
    ]))

    story = [
        _p("Sync License Certificate", _TITLE),
        Spacer(1, 4),
        _p("Issued by oVoxi for the track and tier below.", _SUB),
        Spacer(1, 16),
        table,
        Spacer(1, 18),
    ]
    if lic.get("source") == "subscription" and lic.get("plan"):
        from sync_constants import PLANS
        publish = datetime.fromisoformat(lic["publish_by"]).strftime("%B %d, %Y") if lic.get("publish_by") else ""
        story += [_p(f"Registered under the {PLANS[lic['plan']]['label']} plan. Publish by {publish}.", _SMALL),
                  Spacer(1, 10)]
    story.append(_p("License terms", _H2))
    for b in terms:
        if b["type"] in ("title", "heading"):
            story += [_p(b["text"], _H2)]
        elif b["type"] == "item":
            story += [_p(b["text"], _ITEM), Spacer(1, 4)]
        else:
            story += [_p(b["text"]), Spacer(1, 6)]

    if verify_url:
        story += [Spacer(1, 14), _p("Verification", _H2),
                  _p(f"Verify this license at {verify_url}", _SMALL), Spacer(1, 6), _qr(verify_url)]

    cue = lic.get("cue_sheet") or []
    story += [Spacer(1, 14), _p("Cue sheet information", _H2)]
    if cue:
        head = [_p(h, _LABEL) for h in ("Name", "Role", "PRO", "IPI")]
        body = [[_p(c.get("name")), _p(c.get("role")), _p(c.get("society")), _p(c.get("ipi") or "None")]
                for c in cue]
        cue_table = Table([head, *body], colWidths=[2.3 * inch, 1.3 * inch, 1.6 * inch, 1.5 * inch])
        cue_table.setStyle(TableStyle([
            ("LINEBELOW", (0, 0), (-1, -1), 0.5, RULE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
        story.append(cue_table)
    else:
        story.append(_p("No writer or publisher information on file.", _SMALL))

    story += [Spacer(1, 10), _p(
        f"This certificate is evidence of the license identified by {order['license_id']}. "
        "Keep it with your project files. Contact tyler@ovoxi.net with the License ID for any question.",
        _SMALL)]

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=LETTER, leftMargin=0.8 * inch, rightMargin=0.8 * inch,
                            topMargin=0.8 * inch, bottomMargin=0.8 * inch,
                            title=f"oVoxi license {order['license_id']}", author="oVoxi")

    def on_page(canvas, d):
        _header_bar(canvas, d)
        if order.get("test_mode"):
            _watermark(canvas, d)

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    return buf.getvalue()
