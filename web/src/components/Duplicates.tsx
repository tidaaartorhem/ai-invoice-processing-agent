import { gbp, shortVendor } from '../format';
import type { DuplicatesBundle } from '../types';

export function Duplicates({ bundle }: { bundle: DuplicatesBundle }) {
  const inWeek = bundle.pairs.filter((p) => p.in_review_week);
  const rest = bundle.pairs.filter((p) => !p.in_review_week);
  return (
    <div>
      <div className="grid kpis" style={{ marginBottom: 14 }}>
        <div className="card kpi"><div className="v num">{bundle.scanned_invoices.toLocaleString()}</div><div className="l">Invoices scanned</div></div>
        <div className="card kpi coral"><div className="v num">{bundle.pairs.length}</div><div className="l">Duplicate-risk pairs</div></div>
        <div className="card kpi gold"><div className="v num">{bundle.pairs_touching_week}</div><div className="l">Pairs in this week's queue</div></div>
      </div>

      <div className="card" style={{ marginBottom: 14 }}>
        <h2>Pairs touching this week's queue</h2>
        <p className="hint">Same account, same total to the penny, different invoice numbers, dated within 7 days. The detector flags; a human decides whether it is one order entered twice.</p>
        <table className="data">
          <thead><tr><th>Invoice A</th><th>Invoice B</th><th>Vendor</th><th>Total</th><th>Gap</th></tr></thead>
          <tbody>
            {inWeek.map((p, i) => (
              <tr key={i}>
                <td className="mono">{p.a.invoice_number}<br /><span style={{ color: 'var(--ink-faint)' }}>{p.a.invoice_date}</span></td>
                <td className="mono">{p.b.invoice_number}<br /><span style={{ color: 'var(--ink-faint)' }}>{p.b.invoice_date}</span></td>
                <td>{shortVendor(p.a.vendor_raw)}</td>
                <td className="num"><b>{gbp(p.a.total)}</b></td>
                <td>{p.reason.match(/dates within 7 days/) ? '≤ 7 days' : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="card">
        <h2>All pairs across the corpus year ({rest.length})</h2>
        <p className="hint">The same check, run over every invoice in the corpus — double-billing is a year-round pattern, not a weekly one.</p>
        <div style={{ maxHeight: 420, overflowY: 'auto' }}>
          <table className="data">
            <thead><tr><th>Invoice A</th><th>Invoice B</th><th>Vendor</th><th>Total</th><th>Dates</th></tr></thead>
            <tbody>
              {rest.map((p, i) => (
                <tr key={i}>
                  <td className="mono">{p.a.invoice_number}</td>
                  <td className="mono">{p.b.invoice_number}</td>
                  <td>{shortVendor(p.a.vendor_raw)}</td>
                  <td className="num">{gbp(p.a.total)}</td>
                  <td className="num" style={{ fontSize: 12.5 }}>{p.a.invoice_date} → {p.b.invoice_date}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
