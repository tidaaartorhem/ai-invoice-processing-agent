"""Services package tests for Matchboard."""

from datetime import date

import pytest

from services import actions as A
from services import discounts as D
from services import duplicates as DP
from services import gl as GL
from services import match as M
from services import normalize as N
from services.schema import GoodsReceipt, Invoice, LineItem, PurchaseOrder


def _inv(invoice_id, vendor, number, total, lines=(), terms="", idate=None):
    return Invoice(
        invoice_id=invoice_id,
        vendor_raw=vendor,
        vendor_key=N.vendor_key(vendor),
        invoice_number=number,
        invoice_date=idate,
        due_date=None,
        currency="USD",
        lines=tuple(lines),
        subtotal=None,
        tax=None,
        total=total,
        payment_terms=terms,
        source="corpus",
    )


def _li(desc, qty, price):
    return LineItem(description=desc, qty=qty, unit_price=price)


# ---- normalize -------------------------------------------------------------

def test_vendor_key_collapses_suffixes_and_case():
    assert N.vendor_key("ACME Inc.") == N.vendor_key("Acme, Inc")
    assert N.vendor_key("Staples LLC") == "staples"


def test_money_parses_formats():
    assert N.money("$1,234.56") == 1234.56
    assert N.money("(45.00)") == -45.00
    assert N.money("abc") is None
    assert N.money("") is None


def test_terms_discount_parses_2_10_net_30():
    assert N.parse_terms_discount("2/10 net 30") == (0.02, 10)
    assert N.parse_terms_discount("net 30") is None


# ---- duplicates ------------------------------------------------------------

def test_exact_duplicate_same_vendor_and_number():
    invs = [
        _inv("corpus:1", "Acme Inc", "INV-100", 500.0),
        _inv("corpus:2", "ACME Inc.", "INV-100", 500.0),
        _inv("corpus:3", "Beta LLC", "INV-100", 500.0),
    ]
    pairs = DP.find_exact_duplicates(invs)
    assert len(pairs) == 1
    assert pairs[0].tier == "exact"
    assert {pairs[0].inv_a, pairs[0].inv_b} == {"corpus:1", "corpus:2"}


def test_near_duplicate_same_total_close_dates():
    invs = [
        _inv("corpus:1", "Acme", "INV-100", 500.0, idate=date(2024, 1, 5)),
        _inv("corpus:2", "Acme", "INV-101", 500.0, idate=date(2024, 1, 9)),
        _inv("corpus:3", "Acme", "INV-102", 500.0, idate=date(2024, 3, 1)),
    ]
    pairs = DP.find_near_duplicates(invs)
    assert len(pairs) == 1
    assert pairs[0].tier == "near"


# ---- matching --------------------------------------------------------------

def _po_and_grn():
    po = PurchaseOrder(
        po_number="PO-1", vendor_key=N.vendor_key("Acme"),
        order_date=date(2024, 1, 1),
        lines=(_li("Widget", 10, 5.0),), total=50.0)
    grn = GoodsReceipt(
        grn_number="GRN-1", po_number="PO-1", vendor_key=N.vendor_key("Acme"),
        received_date=date(2024, 1, 10), lines=(_li("Widget", 10, 5.0),))
    return po, grn


def test_clean_three_way_match_passes():
    po, grn = _po_and_grn()
    inv = _inv("corpus:1", "Acme Inc", "INV-1", 50.0,
               lines=[_li("Widget", 10, 5.0)])
    res = M.match_invoice(inv, [po], [grn])
    assert res.po_number == "PO-1"
    assert res.way == "3-way"
    assert res.passed


def test_missing_po_exception():
    inv = _inv("corpus:1", "Nobody", "INV-1", 50.0)
    res = M.match_invoice(inv, [], [])
    assert "missing_po" in res.exception_codes


def test_price_variance_flagged():
    po, grn = _po_and_grn()
    inv = _inv("corpus:1", "Acme", "INV-1", 60.0,
               lines=[_li("Widget", 10, 6.0)])
    res = M.match_invoice(inv, [po], [grn])
    assert "price_variance" in res.exception_codes


def test_qty_not_received_flagged():
    po, grn = _po_and_grn()
    inv = _inv("corpus:1", "Acme", "INV-1", 75.0,
               lines=[_li("Widget", 15, 5.0)])
    res = M.match_invoice(inv, [po], [grn])
    assert "qty_not_received" in res.exception_codes


def test_grn_missing_flagged_when_no_receipt():
    po, _ = _po_and_grn()
    inv = _inv("corpus:1", "Acme", "INV-1", 50.0,
               lines=[_li("Widget", 10, 5.0)])
    res = M.match_invoice(inv, [po], [])
    assert "grn_missing" in res.exception_codes


# ---- gl --------------------------------------------------------------------

def test_gl_suggestion_keyword_rule():
    sugs = GL.suggest([("Office paper and toner", 100.0), ("Printer ink", 50.0)])
    assert sugs[0].gl_code == "6000"
    assert sugs[0].confidence == pytest.approx(1.0)


# ---- discounts --------------------------------------------------------------

def test_discount_capturable_within_window():
    d = D.evaluate(date(2024, 1, 1), 1000.0, "2/10 net 30", date(2024, 1, 5))
    assert d is not None and d.capturable
    assert d.savings == pytest.approx(20.0)
    assert d.days_left == 6


def test_discount_expired():
    d = D.evaluate(date(2024, 1, 1), 1000.0, "2/10 net 30", date(2024, 1, 20))
    assert d is not None and not d.capturable


# ---- actions ---------------------------------------------------------------

def test_recommendation_blocked_on_exact_duplicate():
    po, grn = _po_and_grn()
    inv = _inv("corpus:1", "Acme", "INV-1", 50.0,
               lines=[_li("Widget", 10, 5.0)])
    res = M.match_invoice(inv, [po], [grn])
    pair = DP.DuplicatePair("corpus:0", "corpus:1", "exact", "same vendor+number")
    rec = A.recommend(inv, res, [pair], [], None)
    assert rec.action == "blocked"
    assert rec.priority == 100


def test_recommendation_approve_on_clean_match():
    po, grn = _po_and_grn()
    inv = _inv("corpus:1", "Acme", "INV-1", 50.0,
               lines=[_li("Widget", 10, 5.0)])
    res = M.match_invoice(inv, [po], [grn])
    rec = A.recommend(inv, res, [], [], None)
    assert rec.action == "approve"


def test_rank_orders_by_priority():
    r1 = A.Recommendation("a", "approve", 10, (), (), None)
    r2 = A.Recommendation("b", "blocked", 100, (), (), None)
    assert [r.invoice_id for r in A.rank([r1, r2])] == ["b", "a"]
