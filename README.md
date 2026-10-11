# Matchboard — the invoice review board small businesses never had

Small businesses don't lose money typing invoices into accounting software. They lose it on **invoices that never tie out**.

A vendor emails the same invoice twice and it gets paid twice. A 2%-for-10-days early-payment discount dies in a three-week approval pile — on a £4,000 invoice that's £80 gone, and it's the cheapest money the business will ever be offered. Every vendor formats invoices differently, so matching an invoice against the purchase order and the receiving report is manual, error-prone, and usually skipped. The AP clerk's Monday morning is a stack of PDFs and a gut feeling.

Matchboard is a deterministic invoice-to-pay matching pipeline for that Monday morning. It ingests the week's vendor invoices, normalizes them, and runs the three checks a careful controller would run — 2-way/3-way matching against the PO and goods-receipt registers, duplicate detection across the full invoice history, and early-pay discount math — then gives every invoice **one recommended action** (approve / needs review / blocked) in a ranked queue. Nothing in it pays anything: the human gate is a hard rule, not a setting.

## How it works

`python -m services.main` runs the whole pipeline (deterministic, no models, no external calls):

1. **Ingest + normalize** (`services/corpus.py`, `services/normalize.py`) — 19,960 real invoice line-item records from the UCI Online Retail dataset are cleaned and normalized; vendor names are aliased ("Acme Inc." vs "ACME, Inc." stop being two vendors).
2. **Duplicate scan** (`services/duplicates.py`) — exact duplicates (same vendor + invoice number) block payment; near-duplicates (same vendor, same total to the penny, different numbers, within 7 days) go to human review. Found 195 real pairs in the corpus.
3. **2-way / 3-way match** (`services/match.py`) — each invoice is matched line-by-line against its PO (price variance beyond 2% flags) and against goods receipts (invoiced-before-received flags). Tolerances are explicit constants a controller can tune.
4. **GL suggestions** (`services/gl.py`) — keyword rules over a seeded chart of accounts, every suggestion carrying the rule that fired. No black box.
5. **Discount math** (`services/discounts.py`) — `2/10 net 30` terms become a deadline, days left, capturable savings, and the APR equivalent, so the queue shows exactly what a slow approval costs.
6. **One action per invoice** (`services/actions.py`) — approve, needs review, or blocked, ranked into the Monday queue by priority.

The web UI (React + TypeScript, light mode) is the Monday-morning replay of 2011-10-31: the ranked review queue with per-line match evidence, the duplicates board, the discount savings board, and a **paste-an-invoice** tab where pasted invoice text is field-extracted live in the browser and matched against the shipped registers.

## The replay at a glance

- 530 invoices, £260,555.63 under review; 371 clean approves, 159 need a human.
- The top of the queue: two £4,161.06 invoices from the same account, issued 7 minutes apart — the pair that would have been paid twice.
- £678.06 in early-pay discounts still capturable; £239.10 already lost to slow approvals, itemized by invoice.
- 25 invoices under £50 arrived with no PO — the long tail of one-off vendors, and a case for a low-value approval threshold.

## Data

Invoices are the real UCI Online Retail corpus (unedited); the PO/GRN registers and payment terms are the walkthrough's seeded company records. Full provenance in [`data/README-data.md`](data/README-data.md).

## Run it

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest services/tests/   # 16 tests
.venv/bin/python -m services.main            # regenerates web/public/*.json
cd web && npm install && npm test && npm run build
```

## Project layout

- `services/` — the Python pipeline (extraction, matching, scoring)
- `web/` — the React + TypeScript review board (Vite)
- `data/` — the real invoice corpus + provenance notes
