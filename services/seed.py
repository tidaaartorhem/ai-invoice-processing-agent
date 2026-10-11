"""Seeded company records for the walkthrough: the SME's own ERP extract.

THESE ARE NOT REAL DATA. They are the walkthrough's seeded company
records, built to be consistent with the real invoice corpus:

- purchase_orders.csv / goods_receipts.csv: PO and GRN registers for the
  vendor accounts in the review week. PO lines use the products, quantities,
  and prices the account actually bought in the corpus week (median unit
  price per product), so clean matches are grounded in real transactions.
- vendor_terms: payment terms per account (the corpus carries no terms).

Deliberate exception scenarios (documented here, visible in the queue):
- "price_variance"  account 12748: PO prices set 4% below invoiced prices
  (vendor raised prices after the PO — the classic overcharge).
- "qty_not_received" account 13408: the GRN covers only the first two of
  the account's four invoices (goods for the later invoices arrived after
  the invoice — pay only for what's received).
- "missing_po"  accounts 15516, 12921, 14895: no PO seeded at all.
- "grn_missing" account 16013: PO exists, but no goods receipt on file.

Every other account with 2+ invoices in the review week (or a single
invoice of >= 200 GBP) gets a clean PO + full GRN, so the queue's
approvals are real matches, not fixtures.
"""

from __future__ import annotations

from datetime import date

from .schema import GoodsReceipt, Invoice, LineItem, PurchaseOrder

# account id -> payment terms (seeded vendor master; corpus has no terms)
VENDOR_TERMS: dict[str, str] = {
    "14607": "2/5 net 30",    # aggressive terms, all expired by review -> lost savings
    "12748": "2/10 net 30",
    "13408": "2/10 net 30",
    "16013": "2/10 net 30",
    "15482": "2/10 net 30",   # duplicate-pair accounts
    "12536": "2/10 net 30",
    "17213": "2/10 net 30",
    "13694": "2/10 net 30",
    "17841": "1/10 net 30",
    "14646": "2/10 net 30",
    "17545": "1/10 net 30",
}

DEFAULT_TERMS = "net 30"

# account id -> scenario (see module docstring)
PRICE_VARIANCE_ACCOUNTS = {"12748": 0.96}   # PO price = 96% of invoiced
QTY_SHORTFALL_ACCOUNTS = {"13408"}          # GRN covers first 2 invoices only
MISSING_PO_ACCOUNTS = {"15516", "12921", "14895"}
GRN_MISSING_ACCOUNTS = {"16013"}

PO_SINGLE_INVOICE_MIN = 200.0  # GBP: seed a PO for big one-off invoices too


def _acct(inv: Invoice) -> str | None:
    cid = inv.evidence.get("customer_id")
    return str(cid) if cid else None


def _po_lines_for(invoices: list[Invoice], price_factor: float = 1.0
                  ) -> tuple[LineItem, ...]:
    """Union of products bought, at the prices actually paid."""
    by_desc: dict[str, list[float]] = {}
    qty: dict[str, float] = {}
    for inv in invoices:
        for ln in inv.lines:
            by_desc.setdefault(ln.description, []).append(ln.unit_price)
            qty[ln.description] = qty.get(ln.description, 0.0) + ln.qty
    lines = []
    for desc in sorted(by_desc):
        prices = sorted(by_desc[desc])
        unit = prices[len(prices) // 2] * price_factor
        lines.append(LineItem(description=desc, qty=qty[desc],
                              unit_price=round(unit, 2)))
    return tuple(lines)


def build_terms(invoices: list[Invoice]) -> dict[str, str]:
    """vendor_key -> payment terms for the walkthrough."""
    terms: dict[str, str] = {}
    for inv in invoices:
        acct = _acct(inv)
        if acct is None:
            continue
        terms[inv.vendor_key] = VENDOR_TERMS.get(acct, DEFAULT_TERMS)
    return terms


def build_registers(invoices: list[Invoice]
                    ) -> tuple[list[PurchaseOrder], list[GoodsReceipt]]:
    """Seeded PO + GRN registers consistent with the review-week invoices."""
    by_acct: dict[str, list[Invoice]] = {}
    for inv in invoices:
        acct = _acct(inv)
        if acct is None:
            continue
        by_acct.setdefault(acct, []).append(inv)

    pos: list[PurchaseOrder] = []
    grns: list[GoodsReceipt] = []
    seq = 0
    for acct in sorted(by_acct):
        if acct in MISSING_PO_ACCOUNTS:
            continue  # the missing-PO scenario: vendor billed with no PO
        acct_invs = sorted(by_acct[acct], key=lambda i: (i.invoice_date or date.min,
                                                        i.invoice_number))
        # single small one-off invoices get no PO (long tail, honest missing_po)
        if len(acct_invs) == 1 and (acct_invs[0].total or 0) < PO_SINGLE_INVOICE_MIN:
            continue
        seq += 1
        factor = PRICE_VARIANCE_ACCOUNTS.get(acct, 1.0)
        po_lines = _po_lines_for(acct_invs, price_factor=factor)
        po = PurchaseOrder(
            po_number=f"PO-2011-{seq:04d}",
            vendor_key=acct_invs[0].vendor_key,
            order_date=date(2011, 10, 10),
            lines=po_lines,
            total=round(sum(ln.amount for ln in po_lines), 2),
        )
        pos.append(po)

        if acct in GRN_MISSING_ACCOUNTS:
            continue  # the grn-missing scenario
        if acct in QTY_SHORTFALL_ACCOUNTS:
            # goods for the first two invoices arrived; the rest invoiced early
            grn_lines = _po_lines_for(acct_invs[:2])
        else:
            grn_lines = _po_lines_for(acct_invs)
        grns.append(GoodsReceipt(
            grn_number=f"GRN-2011-{seq:04d}",
            po_number=po.po_number,
            vendor_key=po.vendor_key,
            received_date=date(2011, 10, 20),
            lines=grn_lines,
        ))
    return pos, grns
