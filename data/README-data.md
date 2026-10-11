# Data provenance

## The invoice corpus — real data

`data/raw/Online Retail.xlsx` — 541,909 real invoice line-item rows
(`InvoiceNo`, `StockCode`, `Description`, `Quantity`, `InvoiceDate`,
`UnitPrice`, `CustomerID`, `Country`) from a UK-based online retailer,
December 2010 – December 2011.

Source: the **UCI Online Retail dataset** (Daqing Chen, Sai Liang Sain, and
Kun Guo, 2015), downloaded without authentication from the UCI Machine
Learning Repository
(`https://archive.ics.uci.edu/static/public/352/online+retail.zip`,
23,715,478 bytes, verified 2026-10-11) and bundled here. No synthetic
rows, no edits — the loader (`services/corpus.py`) only:

- drops cancelled invoices (`InvoiceNo` starting with `C` — credit notes,
  9,288 rows, counted separately in analytics),
- drops rows with non-positive quantity/price or no description,
- aggregates repeated product lines inside one invoice,
- caches the cleaned line rows to `data/processed/invoice_lines.csv`.

That leaves 19,960 real invoices. Counterparties in the source are
customer accounts; the walkthrough treats each account as a vendor
account in an AP view (see below).

## The walkthrough replay — Monday 2011-10-31

The UI replays the AP queue **as it stood on the morning of Monday
2011-10-31**: invoices dated 2011-10-24..30 (530 invoices, £260,555.63).
Duplicate detection scans the full year of 19,960 invoices, because
double-billing is a corpus-wide pattern — it found 195 real
duplicate-risk pairs (same account, same total to the penny, different
invoice numbers, dated within 7 days), 3 of which touch the review week.
The headline pair: invoices 573077 and 573080, both £4,161.06 from the
same account, issued 7 minutes apart.

## The company records — seeded for the walkthrough (not real)

`services/seed.py` builds the SME's own ERP extract, clearly labeled in
code and in the UI:

- **Purchase-order register** (318 POs): one per vendor account with 2+
  invoices in the review week (or a single invoice ≥ £200). PO lines use
  the products, quantities, and prices the account *actually* bought that
  week (median unit price per product), so clean matches are grounded in
  real transactions.
- **Goods-receipt register** (317 GRNs): received quantities mirror the
  POs, except for the documented scenarios below.
- **Vendor payment terms**: the corpus carries no terms, so terms are
  seeded per account (e.g. `2/10 net 30`, `net 30`).

Deliberate exception scenarios (documented in `services/seed.py`, visible
in the queue): account 12748 has PO prices 4% below invoiced prices
(vendor raised prices after the PO); account 13408's GRN covers only its
first two invoices (invoiced before receipt); accounts 15516, 12921, 14895
have no PO at all; account 16013 has a PO but no goods receipt.

Derived artifacts (`web/public/*.json`) are regenerated deterministically
by `python -m services.main`.
