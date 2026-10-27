"""Monthly close, Subscription Artist Pool and statements (Brief 27 Part C).

Artist Agreement v5: 7.6 (pool), 8.1 (paid within 45 days of month-end; $25 rollover;
any balance at least once a year), 8.2 (statement contents). Co-owner Consent 3.3:
co-owners without an account get their statement by email.

Close month is safe to run more than once: the pool lines are idempotent, statements
are upserted, and the emails carry an idempotency key.
"""
import calendar
import io
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

import wallet

PAYOUT_MIN_CENTS = 2500     # 8.1: balances below $25 roll over
PAYOUT_DAYS = 45            # 8.1: paid within 45 days after month-end


def month_bounds(period: str):
    y, m = int(period[:4]), int(period[5:7])
    start = datetime(y, m, 1, tzinfo=timezone.utc)
    end = datetime(y + (m == 12), m % 12 + 1, 1, tzinfo=timezone.utc)
    return start, end


def previous_period(now: datetime) -> str:
    first = now.replace(day=1)
    return (first - timedelta(days=1)).strftime("%Y-%m")


def payment_due(period: str) -> str:
    """The date payment for a period is due: 45 days after its last day."""
    y, m = int(period[:4]), int(period[5:7])
    last = datetime(y, m, calendar.monthrange(y, m)[1], tzinfo=timezone.utc)
    return (last + timedelta(days=PAYOUT_DAYS)).date().isoformat()


def fmt_money(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    return f"{sign}${abs(cents) / 100:,.2f}"


def period_label(period: str) -> str:
    y, m = int(period[:4]), int(period[5:7])
    return f"{calendar.month_name[m]} {y}"


def allocate(total_cents: int, counts: dict) -> dict:
    """Pro rata by count, floor each; leftover cents to the largest counts first (ties by key)."""
    n = sum(counts.values())
    if total_cents <= 0 or not n:
        return {k: 0 for k in counts}
    out = {k: total_cents * c // n for k, c in counts.items()}
    left = total_cents - sum(out.values())
    for k in sorted(counts, key=lambda k: (-counts[k], k))[:left]:
        out[k] += 1
    return out


# --------------------------------------------------------------------------- pool (7.6)

async def pool_net_cents(db, period: str) -> int:
    """Subscription Net Revenue received in the month: payments less tax and Stripe fees,
    less refunds and lost disputes (stored as negative rows)."""
    start, end = month_bounds(period)
    rows = await db.subscription_revenue.find(
        {"created_at": {"$gte": start.isoformat(), "$lt": end.isoformat()}}, {"_id": 0}).to_list(100000)
    return sum(int(r.get("amount_cents") or 0) - int(r.get("tax_cents") or 0) - int(r.get("stripe_fee_cents") or 0)
               for r in rows)


async def registered_project_counts(db, period: str) -> dict:
    """7.6(a) and (c): Registered Projects under sync plans that used each track in the month,
    one count per project. Voided projects (refunds, lost disputes) do not count."""
    start, end = month_bounds(period)
    rows = await db.licenses.find(
        {"source": "subscription", "issued_at": {"$gte": start.isoformat(), "$lt": end.isoformat()},
         "status": {"$nin": ["refunded", "void"]}}, {"_id": 0, "track_id": 1}).to_list(100000)
    counts: dict = {}
    for r in rows:
        if r.get("track_id"):
            counts[r["track_id"]] = counts.get(r["track_id"], 0) + 1
    return counts


async def build_pool(db, period: str, *, test_mode: bool, now: datetime) -> dict:
    """Credit the month's sync Artist Pool to each track's payees. The AI training part
    (7.6(b)) has no plans yet (Brief 24) and stays empty."""
    net = max(0, await pool_net_cents(db, period))
    pool = wallet.revenue_share(net, wallet.POOL_BP)
    counts = await registered_project_counts(db, period)
    shares = allocate(pool, counts)
    total_projects = sum(counts.values())
    written = 0
    for track_id, share in shares.items():
        track = await db.track_submissions.find_one({"id": track_id}, {"_id": 0})
        if not track or not share:
            continue
        lines = wallet.split_share(share, rights=track.get("rights") or {}, licensor_user_id=track["clerk_user_id"],
                                   registered_emails=await wallet.registered_emails(db, track_id))
        track_net = net * counts[track_id] // total_projects if total_projects else 0
        written += await wallet.write_lines(
            db, lines, source_type="sub_pool", source_id=f"pool:{period}:sync", track_id=track_id, field="sync",
            period=period, net_cents=track_net, rate_bp=wallet.POOL_BP, test_mode=test_mode, now=now,
            extra={"registered_projects": counts[track_id], "pool_projects": total_projects,
                   "pool_net_cents": net, "pool_cents": pool})
    return {"net_cents": net, "pool_cents": pool, "projects": total_projects, "tracks": len(counts),
            "lines": written}


# --------------------------------------------------------------------------- statements (8.2)

def _kind_label(e: dict) -> str:
    st = e["source_type"]
    if st == "order":
        return "Sync license"
    if st == "sub_pool":
        return "Subscription pool (sync)"
    if st == "exclusive":
        return "Exclusive License"
    if st == "refund":
        return "Refund"
    if st == "dispute":
        return "Chargeback"
    return "Adjustment"


def build_statement(payee: str, period: str, entries: list, balances: dict, titles: dict) -> dict:
    """Every 8.2 item for one payee and period, from that period's ledger lines."""
    rows = []
    for e in sorted(entries, key=lambda e: (titles.get(e["track_id"], ""), e["created_at"])):
        rows.append({
            "track_id": e["track_id"], "track_title": titles.get(e["track_id"], e["track_id"]),
            "kind": _kind_label(e), "field": e.get("field"),
            "gross_cents": e.get("gross_cents"), "fee_cents": e.get("fee_cents"), "tax_cents": e.get("tax_cents"),
            "net_cents": e.get("net_cents"), "rate_bp": e.get("rate_bp"), "share_bp": e.get("share_bp"),
            "registered_projects": e.get("registered_projects"), "pool_projects": e.get("pool_projects"),
            "amount_cents": e["amount_cents"], "status": e["status"], "test_mode": e.get("test_mode", False),
        })
    held = sum(e["amount_cents"] for e in entries if e["status"] == "held")
    return {
        "payee_key": payee, "period": period, "rows": rows,
        "revenue_share_cents": sum(e["amount_cents"] for e in entries),
        "held_cents": held,
        "registered_projects": sum(e.get("registered_projects") or 0 for e in entries if e["source_type"] == "sub_pool"),
        "exclusive_licenses": sum(1 for e in entries if e["source_type"] == "exclusive"),
        "available_cents": balances.get("available_cents", 0),
        "payable_now": balances.get("available_cents", 0) >= PAYOUT_MIN_CENTS or period.endswith("-12"),
        "payment_due": payment_due(period),
    }


def render_statement_pdf(st: dict, *, payee_name: str) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    h = ParagraphStyle("h", fontName="Helvetica-Bold", fontSize=16, leading=20, spaceAfter=4)
    small = ParagraphStyle("s", fontName="Helvetica", fontSize=9, leading=12, textColor=colors.HexColor("#555555"))
    body = ParagraphStyle("b", fontName="Helvetica", fontSize=9.5, leading=12.5)
    cell = ParagraphStyle("c", fontName="Helvetica", fontSize=8, leading=10)
    story = [Paragraph(f"OVOXI Wallet statement: {period_label(st['period'])}", h),
             Paragraph(f"{payee_name}<br/>OVOXI, Inc., 2389 Main St. Ste 100, Glastonbury, CT, 06033, United States", small),
             Spacer(1, 10)]
    head = ["Song", "Type", "Use", "Received", "Fees", "Tax", "Net Revenue", "Rate", "Your split", "Your share"]
    data = [head]
    for r in st["rows"]:
        pool = f" ({r['registered_projects']} of {r['pool_projects']} projects)" if r.get("pool_projects") else ""
        split = f"{(r['share_bp'] or 0) / 100:g}%" if r.get("share_bp") else ""
        data.append([Paragraph(r["track_title"] + (" (test)" if r["test_mode"] else ""), cell),
                     Paragraph(r["kind"] + pool + (" (held)" if r["status"] == "held" else ""), cell),
                     r["field"] or "",
                     fmt_money(r["gross_cents"]) if r.get("gross_cents") is not None else "",
                     fmt_money(r["fee_cents"]) if r.get("fee_cents") is not None else "",
                     fmt_money(r["tax_cents"]) if r.get("tax_cents") is not None else "",
                     fmt_money(r["net_cents"] or 0), f"{(r['rate_bp'] or 0) / 100:g}%", split,
                     fmt_money(r["amount_cents"])])
    if len(data) == 1:
        data.append(["No activity this month", "", "", "", "", "", "", "", "", ""])
    t = Table(data, repeatRows=1, colWidths=[1.25 * inch, 1.15 * inch, 0.45 * inch, 0.65 * inch, 0.5 * inch,
                                             0.5 * inch, 0.7 * inch, 0.4 * inch, 0.5 * inch, 0.65 * inch])
    t.setStyle(TableStyle([("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8), ("FONT", (0, 1), (-1, -1), "Helvetica", 8),
                           ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#BBBBBB")),
                           ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F0F0F0")), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story += [t, Spacer(1, 12)]
    summary = [
        ("Revenue Share for the month", fmt_money(st["revenue_share_cents"])),
        ("Held for a claim (Section 8.5)", fmt_money(st["held_cents"])),
        ("Registered Projects counted in the Artist Pool", str(st["registered_projects"])),
        ("Exclusive Licenses", str(st["exclusive_licenses"])),
        ("Balance available for payment", fmt_money(st["available_cents"])),
        ("Payment due by", st["payment_due"]),
    ]
    for k, v in summary:
        story.append(Paragraph(f"<b>{k}:</b> {v}", body))
    story += [Spacer(1, 8), Paragraph(
        "Net Revenue is the amount received less payment processing fees and taxes (Artist Agreement 7.2). "
        "Balances under $25 roll over to the next month. Payments go to the bank account connected in your "
        "OVOXI Wallet.", small)]
    buf = io.BytesIO()
    SimpleDocTemplate(buf, pagesize=letter, leftMargin=0.6 * inch, rightMargin=0.6 * inch,
                      topMargin=0.7 * inch, bottomMargin=0.7 * inch, title="OVOXI Wallet statement").build(story)
    return buf.getvalue()


def statement_email(st: dict, *, site: str) -> tuple:
    label = period_label(st["period"])
    subject = f"Your OVOXI statement for {label}"
    text = (f"Your OVOXI Wallet statement for {label} is attached.\n\n"
            f"Revenue Share for the month: {fmt_money(st['revenue_share_cents'])}\n"
            f"Balance available for payment: {fmt_money(st['available_cents'])}\n\n"
            "We keep an OVOXI Wallet for your share. Create an account with this email to see it and get paid: "
            f"{site}/signup\n\nBalances under $25 roll over to the next month.\n")
    html = text.replace("\n", "<br/>")
    return subject, html, text


async def close_month(db, period: str, *, test_mode: bool, now: datetime, admin: str,
                      put_object: Callable, send_email: Optional[Callable], site: str,
                      catch_up: Optional[Callable] = None) -> dict:
    """Prepare a month for payment. Never pays anything."""
    _, end = month_bounds(period)
    if now < end:
        raise ValueError(f"{period_label(period)} has not ended yet.")
    caught = await catch_up(period) if catch_up else 0
    pool = await build_pool(db, period, test_mode=test_mode, now=now)
    moved = await db.wallet_entries.update_many(
        {"status": "accrued", "period": {"$lte": period}, "test_mode": test_mode},
        {"$set": {"status": "available", "available_at": now.isoformat()}})
    month = await db.wallet_entries.find({"period": period, "test_mode": test_mode}, {"_id": 0}).to_list(100000)
    by_payee: dict = {}
    for e in month:
        by_payee.setdefault(e["payee_key"], []).append(e)
    titles = {t["id"]: t.get("track_name") or t["id"] for t in await db.track_submissions.find(
        {"id": {"$in": list({e["track_id"] for e in month})}}, {"_id": 0, "id": 1, "track_name": 1}).to_list(10000)}
    sent = 0
    for payee, entries in by_payee.items():
        avail = await db.wallet_entries.find({"payee_key": payee, "status": "available", "test_mode": test_mode},
                                             {"_id": 0, "amount_cents": 1}).to_list(100000)
        st = build_statement(payee, period, entries, {"available_cents": sum(a["amount_cents"] for a in avail)}, titles)
        name = entries[0].get("payee_email") or payee
        pdf = render_statement_pdf(st, payee_name=name)
        key = f"statements/{payee.replace(':', '_')}/{period}{'-test' if test_mode else ''}.pdf"
        await put_object(key, pdf, "application/pdf")
        await db.statements.update_one({"payee_key": payee, "period": period, "test_mode": test_mode},
                                       {"$set": {**st, "pdf_key": key, "test_mode": test_mode,
                                                 "updated_at": now.isoformat()},
                                        "$setOnInsert": {"created_at": now.isoformat()}}, upsert=True)
        if payee.startswith("email:") and send_email:
            subject, html, text = statement_email(st, site=site)
            res = await send_email(to=payee[len("email:"):], subject=subject, html=html, text=text,
                                   attachments=[(f"OVOXI statement {period}.pdf", pdf)],
                                   idempotency_key=f"statement:{period}:{payee}:{int(test_mode)}")
            sent += res.get("status") == "sent"
    summary = {"period": period, "test_mode": test_mode, "pool": pool, "made_available": moved.modified_count,
               "statements": len(by_payee), "emails_sent": sent, "caught_up": caught,
               "closed_at": now.isoformat(), "closed_by": admin}
    await db.wallet_closes.update_one({"period": period, "test_mode": test_mode}, {"$set": summary}, upsert=True)
    return summary
