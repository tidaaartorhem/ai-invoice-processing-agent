/** Field extraction from pasted invoice text — TS port of services/extract.py.
 *  Deterministic regex extraction. Anything it cannot find is reported as
 *  missing rather than invented. */

export interface ExtractedLine {
  description: string;
  qty: number;
  unit_price: number | null;
}

export interface ExtractResult {
  fields: {
    invoice_number?: string;
    invoice_date?: string;
    vendor_raw?: string;
    total?: number | null;
    currency: string;
    payment_terms?: string;
    lines: ExtractedLine[];
  };
  missing: string[];
}

const INV_NO = /(?:invoice\s*(?:no|number|#)\s*[:#]?\s*)([A-Z0-9\-/]+)/i;
const DATE = /(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2})/g;
const TOTAL = /(?:total|amount due|balance due)\s*[:$]?\s*[£$€]?\s*([\d,]+\.\d{2})/i;
const CURRENCY = /([£$€])/;
const LINE = /^(.{3,60}?)\s+(\d+(?:\.\d+)?)\s*[x×]\s*[£$€]?\s*([\d,]+\.\d{2})/gm;
const VENDOR = /(?:from|vendor|bill to|supplier)\s*:\s*(.+)/i;
const TERMS = /((?:\d+\/\d+\s*net\s*\d+|net\s*\d+))/i;

function parseMoney(s: string): number | null {
  const v = parseFloat(s.replace(/[$£€,\s]/g, ''));
  return Number.isNaN(v) ? null : v;
}

function parseDate(s: string): Date | null {
  let m = s.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (m) return new Date(+m[1], +m[2] - 1, +m[3]);
  m = s.match(/^(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})$/);
  if (m) {
    let y = +m[3];
    if (y < 100) y += 2000;
    return new Date(y, +m[2] - 1, +m[1]);
  }
  return null;
}

export function extractInvoiceText(text: string): ExtractResult {
  const missing: string[] = [];
  const fields: ExtractResult['fields'] = { currency: 'GBP', lines: [] };

  const invNo = text.match(INV_NO);
  if (invNo) fields.invoice_number = invNo[1].trim();
  else missing.push('invoice_number');

  const dates = [...text.matchAll(DATE)]
    .map((m) => parseDate(m[1]))
    .filter((d): d is Date => d !== null)
    .sort((a, b) => a.getTime() - b.getTime());
  if (dates.length > 0) fields.invoice_date = dates[0].toISOString().slice(0, 10);
  else missing.push('invoice_date');

  const vendor = text.match(VENDOR);
  if (vendor) fields.vendor_raw = vendor[1].trim().slice(0, 80);
  else missing.push('vendor_raw');

  const total = text.match(TOTAL);
  if (total) fields.total = parseMoney(total[1]);
  else missing.push('total');

  const cur = text.match(CURRENCY);
  if (cur) fields.currency = { '£': 'GBP', $: 'USD', '€': 'EUR' }[cur[1]] ?? 'GBP';

  const terms = text.match(TERMS);
  if (terms) fields.payment_terms = terms[1];

  for (const m of text.matchAll(LINE)) {
    const unit = parseMoney(m[3]);
    if (unit === null) continue;
    fields.lines.push({ description: m[1].trim(), qty: parseFloat(m[2]), unit_price: unit });
  }
  if (fields.lines.length === 0) missing.push('lines');

  return { fields, missing };
}
