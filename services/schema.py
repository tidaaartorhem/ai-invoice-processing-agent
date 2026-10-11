"""Canonical invoice record: what the pipeline reasons about.

The pipeline never cares where an invoice came from (real corpus rows,
seeded company records, pasted data). Every invoice is normalized into one
of these before matching, so extraction, normalization, matching, GL
suggestions, discount math, and actions all stay deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional


@dataclass(frozen=True)
class LineItem:
    description: str
    qty: float
    unit_price: float

    @property
    def amount(self) -> float:
        return round(self.qty * self.unit_price, 2)


@dataclass(frozen=True)
class Invoice:
    """One vendor invoice, normalized."""

    invoice_id: str            # stable id: "<source>:<row>" e.g. "corpus:042"
    vendor_raw: str            # as printed on the invoice
    vendor_key: str            # normalized vendor key (aliasing applied)
    invoice_number: str        # as printed (may be blank in receipt corpora)
    invoice_date: Optional[date]
    due_date: Optional[date]
    currency: str              # ISO 4217, uppercase
    lines: tuple[LineItem, ...] = ()
    subtotal: Optional[float] = None
    tax: Optional[float] = None
    total: Optional[float] = None
    payment_terms: str = ""    # raw terms text, e.g. "2/10 net 30"
    source: str = "corpus"     # "corpus" (real invoices) or "seed" (company ERP extract)
    evidence: dict = field(default_factory=dict, compare=False)


@dataclass(frozen=True)
class PurchaseOrder:
    po_number: str
    vendor_key: str
    order_date: Optional[date]
    lines: tuple[LineItem, ...]
    total: Optional[float] = None


@dataclass(frozen=True)
class GoodsReceipt:
    grn_number: str
    po_number: str
    vendor_key: str
    received_date: Optional[date]
    lines: tuple[LineItem, ...]
