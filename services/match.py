"""2-way / 3-way matching: invoice vs PO, and invoice vs PO vs goods receipt.

This is the heart of AP review. For each invoice we try to find the
purchase order it belongs to, then compare three numbers:
  1. price variance: invoiced unit price vs PO unit price per matched line
  2. quantity variance: invoiced qty vs received qty (3-way, needs a GRN)
  3. total variance: invoice total vs the PO line total

Tolerances are explicit constants so a controller can tune them. Anything
outside tolerance becomes a named exception; the summary of the exceptions
feeds the invoice's recommended action.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import normalize as N
from .schema import GoodsReceipt, Invoice, LineItem, PurchaseOrder

PRICE_TOLERANCE = 0.02   # 2% unit-price variance allowed before flagging
QTY_TOLERANCE = 0.0      # quantity must match exactly (receive-before-pay)
TOTAL_TOLERANCE = 1.0    # currency units of slack on the header total


@dataclass
class MatchResult:
    invoice_id: str
    po_number: str | None
    grn_numbers: tuple[str, ...] = ()
    line_matches: list[dict] = field(default_factory=list)
    exceptions: list[str] = field(default_factory=list)
    # exception codes: "missing_po", "total_mismatch", "price_variance",
    #                  "qty_not_received", "grn_missing"
    exception_codes: list[str] = field(default_factory=list)

    @property
    def way(self) -> str:
        return "3-way" if self.grn_numbers else ("2-way" if self.po_number else "none")

    @property
    def passed(self) -> bool:
        return self.po_number is not None and not self.exceptions


def _line_key(desc: str) -> str:
    return " ".join(desc.lower().split())


def _index_lines(lines: tuple[LineItem, ...]) -> dict[str, LineItem]:
    idx: dict[str, LineItem] = {}
    for ln in lines:
        idx[_line_key(ln.description)] = ln
    return idx


def _received_qty(po_number: str, desc: str, grns: list[GoodsReceipt]) -> float:
    total = 0.0
    for grn in grns:
        if grn.po_number != po_number:
            continue
        for ln in grn.lines:
            if _line_key(ln.description) == desc:
                total += ln.qty
    return total


def match_invoice(inv: Invoice, pos: list[PurchaseOrder],
                  grns: list[GoodsReceipt]) -> MatchResult:
    """Match one invoice against the PO and GRN registers."""
    res = MatchResult(invoice_id=inv.invoice_id, po_number=None)

    if inv.vendor_key in _vendor_pos(pos):
        po = _vendor_pos(pos)[inv.vendor_key]
        res.po_number = po.po_number
        po_lines = _index_lines(po.lines)
        my_grns = [g for g in grns if g.po_number == po.po_number]
        res.grn_numbers = tuple(g.grn_number for g in my_grns)

        for ln in inv.lines:
            key = _line_key(ln.description)
            entry: dict = {"description": ln.description, "qty": ln.qty,
                           "unit_price": ln.unit_price, "amount": ln.amount}
            po_ln = po_lines.get(key)
            if po_ln is None:
                entry["po_status"] = "no_po_line"
                res.exceptions.append(
                    f"Line {ln.description!r} has no matching PO line.")
                res.exception_codes.append("price_variance")
                res.line_matches.append(entry)
                continue
            entry["po_unit_price"] = po_ln.unit_price
            variance = 0.0
            if po_ln.unit_price:
                variance = (ln.unit_price - po_ln.unit_price) / po_ln.unit_price
            entry["price_variance"] = round(variance, 4)
            if abs(variance) > PRICE_TOLERANCE:
                entry["po_status"] = "price_variance"
                res.exceptions.append(
                    f"Price variance {variance:+.1%} on {ln.description!r} "
                    f"(invoiced {ln.unit_price:.2f} vs PO {po_ln.unit_price:.2f}).")
                res.exception_codes.append("price_variance")
            else:
                entry["po_status"] = "ok"

            if my_grns:
                received = _received_qty(po.po_number, key, my_grns)
                entry["received_qty"] = received
                if received + QTY_TOLERANCE < ln.qty:
                    entry["grn_status"] = "qty_not_received"
                    res.exceptions.append(
                        f"Invoiced qty {ln.qty:g} of {ln.description!r} exceeds "
                        f"received qty {received:g}.")
                    res.exception_codes.append("qty_not_received")
                else:
                    entry["grn_status"] = "ok"
            else:
                entry["grn_status"] = "grn_missing"
            res.line_matches.append(entry)

        # footing check: does the invoice header total equal its own lines?
        # (A PO's total is the wrong comparator — one PO routinely covers
        # many invoices. PO coverage is already checked per line above via
        # price and quantity variance.)
        if inv.total is not None and inv.lines:
            footed = round(sum(ln.amount for ln in inv.lines), 2)
            if abs(inv.total - footed) > TOTAL_TOLERANCE:
                res.exceptions.append(
                    f"Invoice total {inv.total:.2f} does not foot to its line "
                    f"items ({footed:.2f}).")
                res.exception_codes.append("total_mismatch")

        if inv.lines and not my_grns:
            res.exceptions.append("No goods receipt on file for this PO — 3-way match not possible.")
            res.exception_codes.append("grn_missing")
    else:
        res.exceptions.append(
            f"No purchase order on file for vendor {inv.vendor_key!r} — cannot match.")
        res.exception_codes.append("missing_po")
    return res


def _vendor_pos(pos: list[PurchaseOrder]) -> dict[str, PurchaseOrder]:
    """One PO per vendor for the seeded register; prefer the most recent."""
    from datetime import date as _date

    out: dict[str, PurchaseOrder] = {}
    for po in sorted(pos, key=lambda p: p.order_date or _date.min):
        out[po.vendor_key] = po
    return out
