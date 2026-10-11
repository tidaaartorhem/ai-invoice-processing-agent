"""Duplicate detection: the invoices that get paid twice.

Two tiers:
- exact: same vendor_key + same normalized invoice number (after stripping
  punctuation/case) — these are almost certainly the same document.
- near: same vendor_key + same total (within 1 cent) + dates within 7 days
  + different invoice numbers — a re-issued invoice for the same charges,
  the classic double-payment shape.

Both return pairs with a human-readable reason; they do not mutate anything.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from . import normalize as N
from .schema import Invoice

NUM_CLEAN = re.compile(r"[^a-z0-9]")


def clean_number(num: str) -> str:
    return NUM_CLEAN.sub("", (num or "").lower())


@dataclass(frozen=True)
class DuplicatePair:
    inv_a: str
    inv_b: str
    tier: str          # "exact" | "near"
    reason: str


def find_exact_duplicates(invoices: list[Invoice]) -> list[DuplicatePair]:
    pairs: list[DuplicatePair] = []
    seen: dict[tuple[str, str], str] = {}
    for inv in invoices:
        num = clean_number(inv.invoice_number)
        if not num:
            continue
        key = (inv.vendor_key, num)
        if key in seen:
            pairs.append(DuplicatePair(
                inv_a=seen[key], inv_b=inv.invoice_id, tier="exact",
                reason=f"Same vendor ({inv.vendor_key}) and same invoice number ({inv.invoice_number}).",
            ))
        else:
            seen[key] = inv.invoice_id
    return pairs


def find_near_duplicates(invoices: list[Invoice]) -> list[DuplicatePair]:
    pairs: list[DuplicatePair] = []
    by_vendor: dict[str, list[Invoice]] = {}
    for inv in invoices:
        by_vendor.setdefault(inv.vendor_key, []).append(inv)
    for vendor, group in by_vendor.items():
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                a, b = group[i], group[j]
                if clean_number(a.invoice_number) == clean_number(b.invoice_number):
                    continue  # already an exact duplicate; not near
                if a.total is None or b.total is None:
                    continue
                if abs(a.total - b.total) > 0.01:
                    continue
                if (a.invoice_date and b.invoice_date and
                        abs((a.invoice_date - b.invoice_date).days) > 7):
                    continue
                pairs.append(DuplicatePair(
                    inv_a=a.invoice_id, inv_b=b.invoice_id, tier="near",
                    reason=(f"Same vendor, same total {a.total:.2f}, "
                            f"dates within 7 days, different invoice numbers "
                            f"({a.invoice_number!r} vs {b.invoice_number!r})."),
                ))
    return pairs


def find_all(invoices: list[Invoice]) -> list[DuplicatePair]:
    exact = find_exact_duplicates(invoices)
    near = find_near_duplicates(invoices)
    return exact + near
