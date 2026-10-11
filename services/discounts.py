"""Early-payment discounts: the money slow approvals leave on the table.

Vendors offering "2/10 net 30" will knock 2% off if you pay within 10 days.
Most small businesses miss it because the invoice sits in an approval pile.
Given an invoice's terms and a review date ("this morning"), compute the
discount that is still capturable and its annualized value, so the queue can
show exactly what a slow approval costs.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from . import normalize as N


@dataclass(frozen=True)
class DiscountOpportunity:
    rate: float            # e.g. 0.02
    discount_days: int     # pay within N days of invoice date
    deadline: date         # last day to capture
    days_left: int         # as of review date (negative = expired)
    savings: float         # currency units
    annualized_rate: float # effective APR of taking the discount
    capturable: bool


def evaluate(invoice_date: date | None, total: float | None, terms: str,
             review_date: date) -> DiscountOpportunity | None:
    parsed = N.parse_terms_discount(terms)
    if parsed is None or invoice_date is None or total is None:
        return None
    rate, days = parsed
    deadline = invoice_date + timedelta(days=days)
    days_left = (deadline - review_date).days
    # annualize: discount / (1 - discount) * 365 / (net - discount_days); net unknown -> use 30
    net = 30
    denom = max(net - days, 1)
    apr = (rate / (1 - rate)) * (365 / denom)
    return DiscountOpportunity(
        rate=rate,
        discount_days=days,
        deadline=deadline,
        days_left=days_left,
        savings=round(total * rate, 2),
        annualized_rate=round(apr, 3),
        capturable=days_left >= 0,
    )
