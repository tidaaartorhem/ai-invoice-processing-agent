"""Field extraction from pasted invoice text (the "paste an invoice" demo).

Deterministic regex extraction — no model, no guessing. It pulls the
fields an AP clerk reads first: invoice number, dates, vendor line,
currency, line items (qty x description @ price), and totals. Anything it
cannot find is reported as missing rather than invented. The extracted
invoice is then run through the same normalize -> match -> recommend
pipeline as the corpus invoices.
"""

from __future__ import annotations

import re
from datetime import date

from . import normalize as N
from .schema import Invoice, LineItem

INV_NO = re.compile(r"(?:invoice\s*(?:no|number|#)\s*[:#]?\s*)([A-Z0-9\-/]+)",
                    re.IGNORECASE)
DATE = re.compile(r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2})")
TOTAL = re.compile(r"(?:total|amount due|balance due)\s*[:$]?\s*[$£€]?\s*([\d,]+\.\d{2})",
                   re.IGNORECASE)
CURRENCY = re.compile(r"([£$€])")
LINE = re.compile(
    r"^(.{3,60}?)\s+(\d+(?:\.\d+)?)\s*[x×]\s*[$£€]?\s*([\d,]+\.\d{2})", re.MULTILINE)
VENDOR = re.compile(r"(?:from|vendor|bill to|supplier)\s*:\s*(.+)", re.IGNORECASE)
TERMS = re.compile(r"((?:\d+/\d+\s*net\s*\d+|net\s*\d+))", re.IGNORECASE)


def extract(text: str) -> dict:
    """Extract structured fields from raw invoice text.

    Returns {"fields": {...}, "missing": [...], "invoice": Invoice | None}.
    """
    fields: dict = {}
    missing: list[str] = []

    m = INV_NO.search(text)
    if m:
        fields["invoice_number"] = m.group(1).strip()
    else:
        missing.append("invoice_number")

    dates = [N.parse_date(d) for d in DATE.findall(text)]
    dates = [d for d in dates if d]
    if dates:
        fields["invoice_date"] = min(dates).isoformat()
    else:
        missing.append("invoice_date")

    m = VENDOR.search(text)
    if m:
        fields["vendor_raw"] = m.group(1).strip()[:80]
    else:
        missing.append("vendor_raw")

    m = TOTAL.search(text)
    if m:
        fields["total"] = N.money(m.group(1))
    else:
        missing.append("total")

    m = CURRENCY.search(text)
    fields["currency"] = {"£": "GBP", "$": "USD", "€": "EUR"}.get(
        m.group(1) if m else "", "GBP")

    m = TERMS.search(text)
    if m:
        fields["payment_terms"] = m.group(1)

    lines = []
    for desc, qty, price in LINE.findall(text):
        try:
            lines.append({"description": desc.strip(), "qty": float(qty),
                          "unit_price": N.money(price)})
        except (TypeError, ValueError):
            continue
    fields["lines"] = lines
    if not lines:
        missing.append("lines")

    invoice = None
    if not missing or set(missing) <= {"lines", "payment_terms"}:
        vendor_raw = fields.get("vendor_raw", "Unknown vendor")
        inv_date = N.parse_date(fields.get("invoice_date", ""))
        lis = tuple(LineItem(description=l["description"], qty=l["qty"],
                             unit_price=l["unit_price"] or 0.0)
                    for l in lines)
        total = fields.get("total")
        if total is None and lis:
            total = round(sum(l.amount for l in lis), 2)
        invoice = Invoice(
            invoice_id="pasted:1",
            vendor_raw=vendor_raw,
            vendor_key=N.vendor_key(vendor_raw),
            invoice_number=fields.get("invoice_number", "UNKNOWN"),
            invoice_date=inv_date,
            due_date=None,
            currency=fields["currency"],
            lines=lis,
            subtotal=total,
            tax=None,
            total=total,
            payment_terms=fields.get("payment_terms", ""),
            source="pasted",
        )
    return {"fields": fields, "missing": missing, "invoice": invoice,
            "extracted_at": date.today().isoformat()}
