import { useState } from 'react';
import { extractInvoiceText } from '../extract';
import { actionLabel, gbp } from '../format';
import {
  recommendPasted, vendorKey, type PastedInvoice, type Registers,
} from '../client-match';
import type { PasteSample } from '../types';

const DEMO_TEXT = `From: Vendor account 12748 (United Kingdom)
Invoice No: 572881
Date: 26/10/2011
HOT WATER BOTTLE KEEP CALM  4 x 5.15
Total: 20.60
Terms: 2/10 net 30`;

export function PasteInvoice({ registers, samples, reviewDate }: {
  registers: Registers; samples: PasteSample[]; reviewDate: string;
}) {
  const [text, setText] = useState(DEMO_TEXT);
  const [ran, setRan] = useState(false);

  const { fields, missing } = extractInvoiceText(text);
  const inv: PastedInvoice = {
    vendor_raw: fields.vendor_raw ?? 'Unknown vendor',
    vendor_key: vendorKey(fields.vendor_raw ?? 'unknown vendor'),
    invoice_number: fields.invoice_number ?? 'UNKNOWN',
    invoice_date: fields.invoice_date ?? null,
    currency: fields.currency,
    total: fields.total ?? (fields.lines.length > 0
      ? Math.round(fields.lines.reduce((s, l) => s + l.qty * (l.unit_price ?? 0), 0) * 100) / 100
      : null),
    lines: fields.lines,
    payment_terms: fields.payment_terms ?? '',
  };
  const rec = recommendPasted(inv, registers, reviewDate);
  const usable = missing.length === 0 || (missing.length === 1 && missing[0] === 'payment_terms');

  return (
    <div>
      <div className="card" style={{ marginBottom: 14 }}>
        <h2>Paste an invoice, watch it get matched</h2>
        <p className="hint">
          The extractor pulls fields with deterministic patterns — nothing is invented. Then the pasted invoice
          runs the same match against the walkthrough's seeded PO register as the corpus invoices.
          Matched only against vendors shipped in the register bundle.
        </p>
        <textarea className="paste" value={text} onChange={(e) => { setText(e.target.value); setRan(false); }} spellCheck={false} />
        <div style={{ display: 'flex', gap: 8, marginTop: 10, flexWrap: 'wrap' }}>
          <button className="btn" onClick={() => setRan(true)}>Extract and match</button>
          {samples.filter((s) => s.result).slice(0, 3).map((s) => (
            <button key={s.title} className="btn ghost" onClick={() => { setText(s.text); setRan(true); }}>{s.title}</button>
          ))}
        </div>
      </div>

      {ran && (
        <div className="grid two">
          <div className="card">
            <h2>Extracted fields</h2>
            <dl className="kv">
              <dt>Invoice #</dt><dd className={fields.invoice_number ? '' : 'missing'}>{fields.invoice_number ?? 'missing'}</dd>
              <dt>Date</dt><dd className={fields.invoice_date ? '' : 'missing'}>{fields.invoice_date ?? 'missing'}</dd>
              <dt>Vendor</dt><dd className={fields.vendor_raw ? '' : 'missing'}>{fields.vendor_raw ?? 'missing'}</dd>
              <dt>Total</dt><dd className={fields.total != null ? '' : 'missing'}>{fields.total != null ? gbp(fields.total) : 'missing'}</dd>
              <dt>Terms</dt><dd>{fields.payment_terms ?? rec.terms_used ?? '—'}</dd>
              <dt>Lines</dt><dd className={fields.lines.length ? '' : 'missing'}>{fields.lines.length ? `${fields.lines.length} found` : 'none found'}</dd>
            </dl>
            {missing.length > 0 && (
              <p className="hint" style={{ marginTop: 8 }}>
                <span className="missing">Missing: {missing.join(', ')}</span> — reported, not guessed.
              </p>
            )}
          </div>
          <div className="card detail">
            <h3>Recommended action <span className={`badge ${rec.action}`}>{actionLabel(rec.action)}</span></h3>
            <p className="hint">Priority {rec.priority}/100 · {rec.match.way}{rec.match.po_number ? ` · ${rec.match.po_number}` : ''}</p>
            <ul className="reasons">
              {rec.reasons.map((r, i) => <li key={i} className={/ready to approve/i.test(r) ? 'good' : 'warn'}>{r}</li>)}
            </ul>
            {rec.gl.length > 0 && (
              <p style={{ fontSize: 13.5 }}>GL: <b className="mono">{rec.gl[0].gl_code}</b> {rec.gl[0].gl_name} · {(rec.gl[0].confidence * 100).toFixed(0)}%</p>
            )}
            {!usable && <p className="hint">Extraction is incomplete — matching ran on partial fields; treat the recommendation as provisional.</p>}
            <div className="gate"><b>Human gate:</b> this recommendation never pays anything on its own.</div>
          </div>
        </div>
      )}
    </div>
  );
}
