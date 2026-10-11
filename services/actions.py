"""One recommended action per invoice + the ranked exception queue.

The human gate is a hard rule: nothing in this product pays anything. Every
invoice gets exactly one recommended action from a deterministic policy:

- approve      — 2/3-way matched within tolerance, no duplicate, no mismatch
- needs review — price/quantity/total variance, near-duplicate, missing PO,
                 no GRN, or GL suggestion below confidence
- blocked      — exact duplicate (would be paid twice)

Priority (0-100) ranks the Monday-morning queue: duplicates and missing POs
first, then variances, then expiring discounts, then clean approves.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import discounts as D
from . import gl as GL
from .duplicates import DuplicatePair
from .match import MatchResult
from .schema import Invoice

ACTION_ORDER = {"blocked": 0, "needs_review": 1, "approve": 2}


@dataclass(frozen=True)
class Recommendation:
    invoice_id: str
    action: str               # "approve" | "needs_review" | "blocked"
    priority: int             # 0-100, higher = review first
    reasons: tuple[str, ...]
    gl_suggestions: tuple[GL.GLSuggestion, ...]
    discount: D.DiscountOpportunity | None


def recommend(inv: Invoice, match: MatchResult, dup_pairs: list[DuplicatePair],
              gl_sugs: list[GL.GLSuggestion],
              discount: D.DiscountOpportunity | None) -> Recommendation:
    reasons: list[str] = []
    action = "approve"
    priority = 10

    for p in dup_pairs:
        if p.tier == "exact":
            action = "blocked"
            reasons.append(f"DUPLICATE: {p.reason} Do not pay until resolved.")
            priority = max(priority, 100)
        elif p.tier == "near":
            if action != "blocked":
                action = "needs_review"
            reasons.append(f"Possible duplicate: {p.reason}")
            priority = max(priority, 90)

    if "missing_po" in match.exception_codes:
        if action == "approve":
            action = "needs_review"
        reasons.append("No purchase order on file for this vendor.")
        priority = max(priority, 80)

    for code, msg in zip(match.exception_codes, match.exceptions):
        if code == "missing_po":
            continue
        if action == "approve":
            action = "needs_review"
        reasons.append(msg)
        bump = {"price_variance": 70, "qty_not_received": 75,
                "total_mismatch": 85, "grn_missing": 50}.get(code, 40)
        priority = max(priority, bump)

    if match.passed and not reasons:
        reasons.append(
            f"{match.way} match clean within tolerance. Ready to approve.")

    # Discounts only make the queue when they are at risk of expiring.
    if discount is not None and discount.capturable:
        if discount.days_left <= 5:
            reasons.append(
                f"Early-pay discount {discount.rate:.0%} expires in "
                f"{discount.days_left}d — worth {discount.savings:.2f} "
                f"({discount.annualized_rate:.0%} APR equivalent).")
            priority = max(priority, 60)
    elif discount is not None:
        reasons.append(
            f"Early-pay discount {discount.rate:.0%} expired "
            f"({abs(discount.days_left)}d past deadline) — {discount.savings:.2f} lost.")
        priority = max(priority, 55)

    return Recommendation(
        invoice_id=inv.invoice_id,
        action=action,
        priority=min(priority, 100),
        reasons=tuple(reasons),
        gl_suggestions=tuple(gl_sugs),
        discount=discount,
    )


def rank(recommendations: list[Recommendation]) -> list[Recommendation]:
    """Order the Monday-morning queue: priority desc, action severity, invoice."""
    return sorted(recommendations,
                  key=lambda r: (-r.priority, ACTION_ORDER[r.action], r.invoice_id))
