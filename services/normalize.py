"""Normalization: vendor aliasing, currency, dates, money.

Two invoices from the same vendor almost never spell the vendor's name the
same way twice ("ACME Inc.", "Acme Inc", "ACME INC."). Every match below
keys on vendor_key, so aliasing has to happen before anything else.
"""

from __future__ import annotations

import re
from datetime import date, datetime

SUFFIXES = re.compile(
    r"\b(inc\.?|ltd\.?|llc|co\.?|corp\.?|corporation|limited|gmbh|s\.?a\.?|pvt\.?|plc)\b",
    re.IGNORECASE,
)
NON_ALNUM = re.compile(r"[^a-z0-9 ]+")
MULTISPACE = re.compile(r"\s+")


def vendor_key(raw: str) -> str:
    """Collapse a vendor name to a stable lowercase key."""
    s = (raw or "").strip().lower()
    s = SUFFIXES.sub("", s)
    s = NON_ALNUM.sub(" ", s)
    return MULTISPACE.sub(" ", s).strip()


def money(value) -> float | None:
    """Parse a money field to a float; None when absent/invalid."""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    if not s:
        return None
    # strip currency symbols, commas, and parenthesized negatives
    neg = s.startswith("(") and s.endswith(")")
    s = s.strip("()")
    s = re.sub(r"[$€£¥₹,\s]", "", s)
    try:
        v = float(s)
    except ValueError:
        return None
    return -v if neg else v


def parse_date(value) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    s = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%d/%m/%Y", "%d-%m-%Y",
                "%Y-%m-%dT%H:%M:%S", "%d %b %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(s.split("T")[0], fmt).date()
        except ValueError:
            continue
    # last resort: bare YYYY-MM-DD prefix
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return None


def parse_terms_discount(terms: str) -> tuple[float, int] | None:
    """Parse "a/b net c" payment terms -> (discount_rate, discount_days).

    e.g. "2/10 net 30" -> (0.02, 10): pay within 10 days, save 2%.
    """
    m = re.search(r"(\d+(?:\.\d+)?)\s*/\s*(\d+)\s*net\s*\d+", (terms or "").lower())
    if not m:
        return None
    return float(m.group(1)) / 100.0, int(m.group(2))
