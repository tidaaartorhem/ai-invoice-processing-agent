"""Pipeline: corpus -> extract/normalize -> match -> recommend -> static JSON.

Run:  python -m services.main
Reads:  data/raw/Online Retail.xlsx (cached to data/processed/invoice_lines.csv)
Writes: web/public/queue.json       ranked Monday-morning review queue (full detail)
        web/public/duplicates.json  corpus-wide duplicate-risk pairs
        web/public/analytics.json   corpus + queue analytics
        web/public/paste_samples.json  sample pasted invoices, extracted
        web/public/meta.json        run metadata (deterministic provenance)

The replay: the AP queue exactly as it stood on the morning of Monday
2011-10-31 (invoices dated 2011-10-24..30). Duplicate detection scans the
full year of invoices because double-billing is a corpus-wide pattern.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import date
from pathlib import Path

from . import actions as A
from . import corpus as C
from . import discounts as D
from . import duplicates as DP
from . import extract as E
from . import gl as GL
from . import match as M
from . import normalize as N
from . import seed as S
from .schema import Invoice

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "web" / "public"

REVIEW_DATE = C.REVIEW_DATE
QUEUE_LIMIT = 150


def _inv_dict(inv: Invoice) -> dict:
    return {
        "invoice_id": inv.invoice_id,
        "vendor_raw": inv.vendor_raw,
        "vendor_key": inv.vendor_key,
        "invoice_number": inv.invoice_number,
        "invoice_date": inv.invoice_date.isoformat() if inv.invoice_date else None,
        "currency": inv.currency,
        "total": inv.total,
        "n_lines": len(inv.lines),
        "lines": [{"description": ln.description, "qty": ln.qty,
                   "unit_price": ln.unit_price, "amount": ln.amount}
                  for ln in inv.lines],
        "source": inv.source,
    }


def _process(inv: Invoice, pos, grns, terms, dup_index) -> dict:
    match = M.match_invoice(inv, pos, grns)
    gl_sugs = GL.suggest([(ln.description, ln.amount) for ln in inv.lines])
    disc = D.evaluate(inv.invoice_date, inv.total,
                      terms.get(inv.vendor_key, ""), REVIEW_DATE)
    rec = A.recommend(inv, match, dup_index.get(inv.invoice_id, []), gl_sugs, disc)
    return {
        "invoice": _inv_dict(inv),
        "match": {
            "po_number": match.po_number,
            "grn_numbers": list(match.grn_numbers),
            "way": match.way,
            "passed": match.passed,
            "exceptions": match.exceptions,
            "exception_codes": match.exception_codes,
            "line_matches": match.line_matches,
        },
        "gl_suggestions": [
            {"gl_code": g.gl_code, "gl_name": g.gl_name,
             "confidence": g.confidence, "reason": g.reason}
            for g in rec.gl_suggestions
        ],
        "discount": None if disc is None else {
            "rate": disc.rate, "discount_days": disc.discount_days,
            "deadline": disc.deadline.isoformat(), "days_left": disc.days_left,
            "savings": disc.savings, "annualized_rate": disc.annualized_rate,
            "capturable": disc.capturable,
        },
        "recommendation": {
            "action": rec.action,
            "priority": rec.priority,
            "reasons": list(rec.reasons),
        },
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    print("[main] loading corpus...")
    all_invoices = C.load_all()
    window = C.load_window()
    print(f"[main] {len(all_invoices)} invoices in corpus, {len(window)} in review week")

    print("[main] building seeded company records...")
    pos, grns = S.build_registers(window)
    terms = S.build_terms(window)
    print(f"[main] {len(pos)} POs, {len(grns)} GRNs, {len(terms)} vendor term rows")

    print("[main] scanning for duplicates (corpus-wide)...")
    pairs = DP.find_all(all_invoices)
    by_id: dict[str, list[Invoice]] = {i.invoice_id: i for i in all_invoices}
    dup_index: dict[str, list[DP.DuplicatePair]] = {}
    for p in pairs:
        dup_index.setdefault(p.inv_a, []).append(p)
        dup_index.setdefault(p.inv_b, []).append(p)
    window_ids = {i.invoice_id for i in window}
    pairs_touching = [p for p in pairs
                      if p.inv_a in window_ids or p.inv_b in window_ids]
    print(f"[main] {len(pairs)} duplicate-risk pairs corpus-wide, "
          f"{len(pairs_touching)} touch the review week")

    print("[main] matching + recommending the review week...")
    processed = [_process(inv, pos, grns, terms, dup_index) for inv in window]
    recs = []
    for p, inv in zip(processed, window):
        r = p["recommendation"]
        recs.append((r["priority"], r["action"], inv.invoice_id))
    order = A.rank([A.Recommendation(iid, a, pr, (), (), None)
                    for pr, a, iid in recs])
    rank_index = {r.invoice_id: n for n, r in enumerate(order)}
    processed.sort(key=lambda p: rank_index[p["invoice"]["invoice_id"]])

    queue = processed[:QUEUE_LIMIT]
    (OUT / "queue.json").write_text(json.dumps({
        "review_date": REVIEW_DATE.isoformat(),
        "window": [C.WINDOW_START.isoformat(), C.WINDOW_END.isoformat()],
        "queue_size": len(processed),
        "shipped": len(queue),
        "items": queue,
    }, indent=1))

    dup_json = []
    for p in pairs:
        for iid in (p.inv_a, p.inv_b):
            pass
        a, b = by_id[p.inv_a], by_id[p.inv_b]
        dup_json.append({
            "tier": p.tier, "reason": p.reason,
            "in_review_week": p in pairs_touching,
            "a": {"invoice_id": a.invoice_id, "invoice_number": a.invoice_number,
                  "vendor_raw": a.vendor_raw,
                  "invoice_date": a.invoice_date.isoformat() if a.invoice_date else None,
                  "total": a.total},
            "b": {"invoice_id": b.invoice_id, "invoice_number": b.invoice_number,
                  "vendor_raw": b.vendor_raw,
                  "invoice_date": b.invoice_date.isoformat() if b.invoice_date else None,
                  "total": b.total},
        })
    (OUT / "duplicates.json").write_text(json.dumps({
        "scanned_invoices": len(all_invoices),
        "pairs": dup_json,
        "pairs_touching_week": len(pairs_touching),
    }, indent=1))

    actions = Counter(p["recommendation"]["action"] for p in processed)
    exc = Counter(c for p in processed for c in p["match"]["exception_codes"])
    capturable = sum(p["discount"]["savings"] for p in processed
                     if p["discount"] and p["discount"]["capturable"])
    lost = sum(p["discount"]["savings"] for p in processed
               if p["discount"] and not p["discount"]["capturable"])
    value_by_action = Counter()
    for p in processed:
        value_by_action[p["recommendation"]["action"]] += p["invoice"]["total"] or 0
    spend = Counter()
    for inv in window:
        spend[inv.vendor_raw] += inv.total or 0
    no_po_small = [p for p in processed
                   if p["match"]["exception_codes"] == ["missing_po"]
                   and (p["invoice"]["total"] or 0) < 50]
    (OUT / "analytics.json").write_text(json.dumps({
        "corpus_invoices": len(all_invoices),
        "window_invoices": len(window),
        "window_spend": round(sum(i.total or 0 for i in window), 2),
        "currency": "GBP",
        "actions": dict(actions),
        "value_by_action": {k: round(v, 2) for k, v in value_by_action.items()},
        "exceptions": dict(exc),
        "discount_capturable": round(capturable, 2),
        "discount_lost": round(lost, 2),
        "top_vendors": [{"vendor": v, "spend": round(s, 2)}
                        for v, s in spend.most_common(10)],
        "no_po_under_50": {"count": len(no_po_small),
                           "spend": round(sum(p["invoice"]["total"] or 0
                                              for p in no_po_small), 2)},
        "pos_seeded": len(pos),
        "grns_seeded": len(grns),
    }, indent=1))

    samples = [
        ("Clean vendor invoice",
         "From: Vendor account 14607 (United Kingdom)\n"
         "Invoice # 572324  Date: 24/10/2011\n"
         "WHITE HANGING HEART T-LIGHT HOLDER  6 x 2.55\n"
         "Total: 15.30\nTerms: 2/10 net 30"),
        ("No extractable number",
         "Some random email text about a meeting tomorrow at 3pm."),
        ("Price-changed invoice",
         "Vendor: Vendor account 12748 (United Kingdom)\n"
         "Invoice No: 572881\nDate: 26/10/2011\n"
         "HOT WATER BOTTLE KEEP CALM  4 x 5.15\n"
         "Total: 20.60\nTerms: 2/10 net 30"),
    ]
    paste_out = []
    for title, text in samples:
        res = E.extract(text)
        entry = {"title": title, "text": text, "fields": res["fields"],
                 "missing": res["missing"]}
        if res["invoice"] is not None:
            proc = _process(res["invoice"], pos, grns, terms, {})
            entry["result"] = proc
        paste_out.append(entry)
    (OUT / "paste_samples.json").write_text(json.dumps(paste_out, indent=1))

    (OUT / "meta.json").write_text(json.dumps({
        "project": "matchboard",
        "review_date": REVIEW_DATE.isoformat(),
        "window": [C.WINDOW_START.isoformat(), C.WINDOW_END.isoformat()],
        "corpus": ("UCI Online Retail (Daqing Chen et al., 2015) — real invoice "
                   "line-item records, UK online retailer, Dec 2010 - Dec 2011. "
                   "Downloaded without auth from the UCI ML Repository."),
        "company_records": ("Seeded PO/GRN registers + vendor terms for the "
                            "walkthrough (see services/seed.py)."),
        "pipeline": "deterministic, no ML models, no external calls",
        "generated_by": "python -m services.main",
    }, indent=1))

    # Seeded company records bundle for the live paste-an-invoice tab.
    # Trimmed to the vendors in the shipped queue to keep the bundle lean.
    queue_vendors = {p["invoice"]["vendor_key"] for p in queue}
    queue_pos = [po for po in pos if po.vendor_key in queue_vendors]
    queue_po_numbers = {po.po_number for po in queue_pos}
    (OUT / "registers.json").write_text(json.dumps({
        "label": "SEEDED company records for the walkthrough (not real data)",
        "review_date": REVIEW_DATE.isoformat(),
        "terms": {k: v for k, v in terms.items() if k in queue_vendors},
        "purchase_orders": [
            {"po_number": po.po_number, "vendor_key": po.vendor_key,
             "order_date": po.order_date.isoformat() if po.order_date else None,
             "lines": [{"description": ln.description, "qty": ln.qty,
                        "unit_price": ln.unit_price} for ln in po.lines]}
            for po in queue_pos
        ],
        "goods_receipts": [
            {"grn_number": g.grn_number, "po_number": g.po_number,
             "vendor_key": g.vendor_key,
             "received_date": g.received_date.isoformat() if g.received_date else None,
             "lines": [{"description": ln.description, "qty": ln.qty,
                        "unit_price": ln.unit_price} for ln in g.lines]}
            for g in grns if g.po_number in queue_po_numbers
        ],
    }, indent=1))
    print("[main] wrote queue/duplicates/analytics/paste_samples/meta/registers to web/public/")


if __name__ == "__main__":
    main()
