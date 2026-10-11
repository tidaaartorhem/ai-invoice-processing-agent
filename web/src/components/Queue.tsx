import { useMemo, useState } from 'react';
import { actionLabel, gbp, pct, shortVendor } from '../format';
import type { ActionKind, QueueBundle, QueueItem } from '../types';

const EXC_LABELS: Record<string, string> = {
  missing_po: 'No PO', price_variance: 'Price variance', qty_not_received: 'Short shipment',
  total_mismatch: 'Total mismatch', grn_missing: 'No GRN',
};

function reasonTone(r: string): string {
  if (/duplicate/i.test(r)) return 'bad';
  if (/ready to approve/i.test(r)) return 'good';
  return 'warn';
}

export function InvoiceDetail({ item, onClose }: { item: QueueItem; onClose: () => void }) {
  const { invoice, match, gl_suggestions, discount, recommendation } = item;
  return (
    <div className="card detail" style={{ marginTop: 14 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <h3>Invoice {invoice.invoice_number} <span className={`badge ${recommendation.action}`}>{actionLabel(recommendation.action)}</span></h3>
          <p className="hint">{invoice.vendor_raw} · {invoice.invoice_date} · {invoice.n_lines} lines · {match.way}{match.po_number ? ` · ${match.po_number}` : ''}</p>
        </div>
        <button className="btn ghost" onClick={onClose}>Close</button>
      </div>

      <ul className="reasons">
        {recommendation.reasons.map((r, i) => (
          <li key={i} className={reasonTone(r)}>{r}</li>
        ))}
      </ul>

      <div className="grid two">
        <div>
          <h2>Line items vs PO</h2>
          <table className="data">
            <thead><tr><th>Description</th><th>Qty</th><th>Invoiced</th><th>PO price</th><th>Status</th></tr></thead>
            <tbody>
              {match.line_matches.map((lm, i) => (
                <tr key={i}>
                  <td>{lm.description}</td>
                  <td className="num">{lm.qty}{lm.received_qty !== undefined ? ` / rcvd ${lm.received_qty}` : ''}</td>
                  <td className="num">{gbp(lm.unit_price)}</td>
                  <td className="num">{lm.po_unit_price !== undefined ? gbp(lm.po_unit_price) : '—'}</td>
                  <td>
                    {lm.po_status === 'ok' ? <span className="ok">ok</span>
                      : lm.po_status ? <span className="missing">{lm.po_status.replace(/_/g, ' ')}{lm.price_variance !== undefined ? ` (${pct(lm.price_variance, 1)})` : ''}</span>
                      : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div>
          <h2>GL suggestion</h2>
          {gl_suggestions.length === 0 && <p className="hint">No keyword rule fires on these lines — code manually.</p>}
          {gl_suggestions.map((g) => (
            <p key={g.gl_code} style={{ fontSize: 13.5 }}>
              <b className="mono">{g.gl_code}</b> {g.gl_name} · {pct(g.confidence, 0)}<br />
              <span style={{ color: 'var(--ink-soft)' }}>{g.reason}</span>
            </p>
          ))}
          <h2 style={{ marginTop: 14 }}>Early-pay discount</h2>
          {discount ? (
            <p style={{ fontSize: 13.5 }}>
              {discount.capturable
                ? <span><b className="ok">{gbp(discount.savings)} capturable</b> — {(discount.rate * 100).toFixed(0)}% if paid by {discount.deadline} ({discount.days_left}d left, {(discount.annualized_rate * 100).toFixed(0)}% APR equivalent).</span>
                : <span><b className="missing">{gbp(discount.savings)} lost</b> — {(discount.rate * 100).toFixed(0)}% discount expired {Math.abs(discount.days_left)}d ago.</span>}
            </p>
          ) : <p className="hint">No discount terms on this invoice.</p>}
          <dl className="kv" style={{ marginTop: 10 }}>
            <dt>Invoice total</dt><dd className="num"><b>{gbp(invoice.total)}</b></dd>
            <dt>Priority</dt><dd className="num">{recommendation.priority} / 100</dd>
          </dl>
        </div>
      </div>

      <div className="gate">
        <b>Human gate:</b> Matchboard never pays anything. The recommended action is <b>{actionLabel(recommendation.action)}</b> — a person approves, investigates, or blocks.
      </div>
    </div>
  );
}

export function Queue({ bundle }: { bundle: QueueBundle }) {
  const [actionFilter, setActionFilter] = useState<'all' | ActionKind>('all');
  const [excFilter, setExcFilter] = useState<string>('all');
  const [selected, setSelected] = useState<QueueItem | null>(null);

  const items = useMemo(() => bundle.items.filter((it) => {
    if (actionFilter !== 'all' && it.recommendation.action !== actionFilter) return false;
    if (excFilter !== 'all' && !it.match.exception_codes.includes(excFilter)) return false;
    return true;
  }), [bundle, actionFilter, excFilter]);

  const excOptions = useMemo(() => {
    const s = new Set<string>();
    bundle.items.forEach((it) => it.match.exception_codes.forEach((c) => s.add(c)));
    return [...s];
  }, [bundle]);

  return (
    <div>
      <div className="card" style={{ marginBottom: 14 }}>
        <h2>Monday-morning queue — {bundle.review_date}</h2>
        <p className="hint">
          {bundle.queue_size} invoices from {bundle.window[0]} to {bundle.window[1]}, ranked by what needs a human first.
          Showing {items.length} of the top {bundle.shipped} shipped with full evidence.
        </p>
        <div className="filters">
          <select value={actionFilter} onChange={(e) => setActionFilter(e.target.value as 'all' | ActionKind)} aria-label="Filter by action">
            <option value="all">All actions</option>
            <option value="needs_review">Needs review</option>
            <option value="approve">Approve</option>
            <option value="blocked">Blocked</option>
          </select>
          <select value={excFilter} onChange={(e) => setExcFilter(e.target.value)} aria-label="Filter by exception">
            <option value="all">All exceptions</option>
            {excOptions.map((c) => <option key={c} value={c}>{EXC_LABELS[c] ?? c}</option>)}
          </select>
        </div>
        <div style={{ overflowX: 'auto' }}>
          <table className="data">
            <thead><tr><th>#</th><th>Invoice</th><th>Vendor</th><th>Total</th><th>Action</th><th>Exceptions</th></tr></thead>
            <tbody>
              {items.map((it, i) => (
                <tr key={it.invoice.invoice_id} className={`rowlink${selected?.invoice.invoice_id === it.invoice.invoice_id ? ' selected' : ''}`}
                    onClick={() => setSelected(it)}>
                  <td className="num">{i + 1}</td>
                  <td className="mono">{it.invoice.invoice_number}<br /><span style={{ color: 'var(--ink-faint)' }}>{it.invoice.invoice_date}</span></td>
                  <td>{shortVendor(it.invoice.vendor_raw)}</td>
                  <td className="num"><b>{gbp(it.invoice.total)}</b></td>
                  <td><span className={`badge ${it.recommendation.action}`}>{actionLabel(it.recommendation.action)}</span></td>
                  <td>{it.match.exception_codes.length === 0
                    ? <span className="ok">clean {it.match.way}</span>
                    : it.match.exception_codes.map((c) => <span key={c} className="badge exc">{EXC_LABELS[c] ?? c}</span>)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      {selected && <InvoiceDetail item={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}
