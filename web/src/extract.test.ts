import { describe, expect, it } from 'vitest';
import { extractInvoiceText } from './extract';

const SAMPLE = `From: Vendor account 14607 (United Kingdom)
Invoice # 572324  Date: 24/10/2011
WHITE HANGING HEART T-LIGHT HOLDER  6 x 2.55
Total: 15.30
Terms: 2/10 net 30`;

describe('extractInvoiceText', () => {
  it('extracts number, date, vendor, total, terms and lines', () => {
    const { fields, missing } = extractInvoiceText(SAMPLE);
    expect(fields.invoice_number).toBe('572324');
    expect(fields.invoice_date).toBe('2011-10-24');
    expect(fields.vendor_raw).toBe('Vendor account 14607 (United Kingdom)');
    expect(fields.total).toBeCloseTo(15.3);
    expect(fields.payment_terms).toBe('2/10 net 30');
    expect(fields.lines).toHaveLength(1);
    expect(fields.lines[0]).toMatchObject({ description: 'WHITE HANGING HEART T-LIGHT HOLDER', qty: 6, unit_price: 2.55 });
    expect(missing).toEqual([]);
  });

  it('reports missing fields instead of inventing them', () => {
    const { fields, missing } = extractInvoiceText('see you at the meeting tomorrow');
    expect(missing).toContain('invoice_number');
    expect(missing).toContain('invoice_date');
    expect(missing).toContain('vendor_raw');
    expect(missing).toContain('total');
    expect(missing).toContain('lines');
    expect(fields.lines).toEqual([]);
  });

  it('detects currency symbols', () => {
    const { fields } = extractInvoiceText('Invoice # 1\nDate: 01/01/2020\nWIDGET  2 x $4.00\nTotal: $8.00');
    expect(fields.currency).toBe('USD');
  });
});
