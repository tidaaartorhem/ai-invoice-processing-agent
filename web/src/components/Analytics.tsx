import { gbp, shortVendor } from '../format';
import type { AnalyticsBundle } from '../types';

const EXC_LABELS: Record<string, string> = {
  missing_po: 'No purchase order', price_variance: 'Price variance vs PO',
  qty_not_received: 'Invoiced before receipt', total_mismatch: 'Total does not foot',
  grn_missing: 'No goods receipt',
};

export function Analytics({ bundle: a, meta }: { bundle: AnalyticsBundle; meta: { corpus: string; company_records: string } }) {
  const totalExc = Object.values(a.exceptions).reduce((s, v) => s + v, 0);
  const maxSpend = Math.max(...a.top_vendors.map((v) => v.spend));
  return (
    <div>
      <div className="grid kpis" style={{ marginBottom: 14 }}>
        <div className="card kpi"><div className="v num">{a.corpus_invoices.toLocaleString()}</div><div className="l">Real invoices in corpus</div></div>
        <div className="card kpi"><div className="v num">{a.window_invoices}</div><div className="l">Invoices this week</div></div>
        <div className="card kpi"><div className="v num">{gbp(a.window_spend)}</div><div className="l">Week's spend</div></div>
        <div className="card kpi gold"><div className="v num">{a.actions['needs_review'] ?? 0}</div><div className="l">Need a human</div></div>
        <div className="card kpi teal"><div className="v num">{a.actions['approve'] ?? 0}</div><div className="l">Clean approves</div></div>
      </div>

      <div className="grid two">
        <div className="card">
          <h2>Where the week breaks</h2>
          <p className="hint">Exception counts across the review week's invoices.</p>
          {Object.entries(a.exceptions).sort((x, y) => y[1] - x[1]).map(([code, n]) => (
            <div key={code} style={{ marginBottom: 10 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13.5 }}>
                <span>{EXC_LABELS[code] ?? code}</span><b className="num">{n}</b>
              </div>
              <div className="bar"><span style={{ width: `${(n / totalExc) * 100}%`, background: 'var(--orange)' }} /></div>
            </div>
          ))}
          <p className="hint" style={{ marginTop: 12 }}>
            {a.no_po_under_50.count} invoices under £50 arrived with no PO ({gbp(a.no_po_under_50.spend)} total) —
            the long tail of one-off vendors, and a case for a low-value no-PO approval threshold.
          </p>
        </div>
        <div className="card">
          <h2>Top vendors by week's spend</h2>
          <p className="hint">Concentration risk at a glance.</p>
          {a.top_vendors.map((v) => (
            <div key={v.vendor} style={{ marginBottom: 10 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13.5 }}>
                <span>{shortVendor(v.vendor)}</span><b className="num">{gbp(v.spend)}</b>
              </div>
              <div className="bar"><span style={{ width: `${(v.spend / maxSpend) * 100}%`, background: 'var(--teal)' }} /></div>
            </div>
          ))}
        </div>
      </div>

      <div className="card" style={{ marginTop: 14 }}>
        <h2>Data provenance</h2>
        <p className="hint" style={{ marginBottom: 6 }}><b>Invoices:</b> {meta.corpus}</p>
        <p className="hint" style={{ marginBottom: 6 }}><b>Company records:</b> {meta.company_records}</p>
        <p className="hint">The invoice records are unedited; the PO/GRN registers and payment terms are the walkthrough's seeded ERP extract, documented in <span className="mono">services/seed.py</span>.</p>
      </div>
    </div>
  );
}
