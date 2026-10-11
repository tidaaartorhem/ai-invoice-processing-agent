"""Corpus loader: real invoice line-item records -> canonical Invoices.

Source: the UCI Online Retail dataset (Daqing Chen et al., 2015) — real
invoice line-item records (InvoiceNo, StockCode, Description, Quantity,
InvoiceDate, UnitPrice, CustomerID, Country) from a UK-based online
retailer, Dec 2010 – Dec 2011. Downloaded without auth from the UCI ML
Repository and bundled at data/raw/Online Retail.xlsx; first run caches the
cleaned line rows to data/processed/invoice_lines.csv so the pipeline does
not re-parse the workbook every time.

What the loader does (deterministic, no edits to the records themselves):
- drops cancelled invoices (InvoiceNo starting with "C" — credit notes,
  counted separately for analytics),
- drops rows with non-positive quantity/price or no description,
- aggregates repeated product lines inside one invoice,
- treats CustomerID as the counterparty account; rows with no CustomerID
  become "No account on file" (they can never match a PO — the pipeline
  says so explicitly instead of guessing).

The walkthrough replays the AP queue as it stood on the morning of
Monday 2011-10-31: invoices dated 2011-10-24..30. Duplicate detection
scans the full year of invoices (18,532), because double-billing is a
corpus-wide pattern, not a weekly one.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from . import normalize as N
from .schema import Invoice, LineItem

ROOT = Path(__file__).resolve().parent.parent
XLSX = ROOT / "data" / "raw" / "Online Retail.xlsx"
CACHE = ROOT / "data" / "processed" / "invoice_lines.csv"

# The Monday-morning replay.
REVIEW_DATE = date(2011, 10, 31)
WINDOW_START = date(2011, 10, 24)
WINDOW_END = date(2011, 10, 30)  # inclusive


def _clean_rows() -> pd.DataFrame:
    if CACHE.exists():
        df = pd.read_csv(CACHE, parse_dates=["invoice_date"],
                         dtype={"invoice_no": str, "cust": str, "stock_code": str})
        df["invoice_date"] = pd.to_datetime(df["invoice_date"]).dt.date
        return df
    raw = pd.read_excel(XLSX)
    raw["InvoiceDate"] = pd.to_datetime(raw["InvoiceDate"])
    cancelled = raw["InvoiceNo"].astype(str).str.startswith("C")
    n_cancelled = int(cancelled.sum())
    df = raw[~cancelled].copy()
    df = df[(df["Quantity"] > 0) & (df["UnitPrice"] > 0)]
    df = df[df["Description"].notna()].copy()
    df["Description"] = df["Description"].astype(str).str.strip()
    df = df[df["Description"] != ""]
    df["cust"] = df["CustomerID"].fillna(0).astype(int).astype(str)
    df["invoice_date"] = df["InvoiceDate"].dt.date
    df["line_total"] = df["Quantity"] * df["UnitPrice"]
    out = df[["InvoiceNo", "cust", "Country", "invoice_date", "StockCode",
              "Description", "Quantity", "UnitPrice", "line_total"]].copy()
    out.columns = ["invoice_no", "cust", "country", "invoice_date", "stock_code",
                   "description", "qty", "unit_price", "line_total"]
    out["invoice_no"] = out["invoice_no"].astype(str)
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(CACHE, index=False)
    print(f"[corpus] cached {len(out)} clean line rows "
          f"({n_cancelled} cancelled rows excluded)")
    return out


def _to_invoice(invoice_no: str, group: pd.DataFrame) -> Invoice:
    cust = str(group["cust"].iloc[0])
    country = str(group["country"].iloc[0])
    if cust == "0":
        vendor_raw = "No account on file"
    else:
        vendor_raw = f"Vendor account {cust} ({country})"
    # aggregate repeated product lines within the invoice
    agg = (group.groupby("description", as_index=False)
           .agg(qty=("qty", "sum"), unit_price=("unit_price", "median")))
    lines = tuple(
        LineItem(description=r.description, qty=float(r.qty),
                 unit_price=float(r.unit_price))
        for r in agg.itertuples()
    )
    total = round(float(group["line_total"].sum()), 2)
    inv_date = group["invoice_date"].iloc[0]
    if hasattr(inv_date, "date"):
        inv_date = inv_date.date()
    return Invoice(
        invoice_id=f"corpus:{invoice_no}",
        vendor_raw=vendor_raw,
        vendor_key=N.vendor_key(vendor_raw),
        invoice_number=invoice_no,
        invoice_date=inv_date,
        due_date=None,
        currency="GBP",
        lines=lines,
        subtotal=total,
        tax=None,  # the source has no tax column; totals are line sums
        total=total,
        payment_terms="",  # terms live in the seeded vendor master (seed.py)
        source="corpus",
        evidence={"country": country, "customer_id": None if cust == "0" else cust,
                  "n_raw_lines": int(len(group))},
    )


def load_all() -> list[Invoice]:
    """Every valid invoice in the corpus (for corpus-wide duplicate scans)."""
    df = _clean_rows()
    return [_to_invoice(no, g) for no, g in df.groupby("invoice_no", sort=False)]


def load_window() -> list[Invoice]:
    """Invoices in the Monday-morning review week."""
    df = _clean_rows()
    win = df[(df["invoice_date"] >= WINDOW_START) & (df["invoice_date"] <= WINDOW_END)]
    return [_to_invoice(no, g) for no, g in win.groupby("invoice_no", sort=False)]
