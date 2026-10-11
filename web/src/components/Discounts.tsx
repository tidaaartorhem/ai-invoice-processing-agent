import { gbp, shortVendor } from '../format';
import type { QueueBundle } from '../types';

export function Discounts({ bundle }: { bundle: QueueBundle }) {
  const withDisc = bundle.items.filter((it) => it.discount);
  const capturable = withDisc.filter((it) => it.discount!.capturable)
    .sort((a, b) => a.discount!.days_left - b.discount!.days_left);
  const lost = withDisc.filter((it) => !it.discount!.capturable)
    .sort((a, b) => (b.discount!.savings - a.discount!.savings));

  return (
    <div>
      <div className="grid kpis" style={{ marginBottom: 14 }}>
        <div className="card kpi teal"><div className="v num">{gbp(capturable.reduce((s, it) => s + it.discount!.savings, 0))}</div><div className="l">Still capturable</div></div>
        <div className="card kpi coral"><div className="v num">{gbp(lost.reduce((s, it) => s + it.discount!.savings, 0))}</div><div className="l">Already lost to slow approvals</div></div>
        <div className="card kpi"><div className="v num">{withDisc.length}</div><div className="l">Invoices with discount terms</div></div>
      </div>

      <div className="grid two">
        <div className="card">
          <h2>Capture before the deadline</h2>
          <p className="hint">Sorted by days left. A 2% ten-day discount is a ~36% APR loan you are giving the vendor — paying fast is the cheapest money there is.</p>
          <table className="data">
            <thead><tr><th>Invoice</th><th>Vendor</th><th>Saves</th><th>Deadline</th></tr></thead>
            <tbody>
              {capturable.slice(0, 20).map((it) => (
                <tr key={it.invoice.invoice_id}>
                  <td className="mono">{it.invoice.invoice_number}</td>
                  <td>{shortVendor(it.invoice.vendor_raw)}</td>
                  <td className="num"><b className="ok">{gbp(it.discount!.savings)}</b></td>
                  <td className="num">{it.discount!.deadline} <span className={it.discount!.days_left <= 3 ? 'missing' : ''}>({it.discount!.days_left}d)</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="card">
          <h2>Missed this week</h2>
          <p className="hint">Discount windows that closed while the invoice sat in the pile. This is the cost of slow approvals, itemized.</p>
          <table className="data">
            <thead><tr><th>Invoice</th><th>Vendor</th><th>Lost</th><th>Expired</th></tr></thead>
            <tbody>
              {lost.slice(0, 20).map((it) => (
                <tr key={it.invoice.invoice_id}>
                  <td className="mono">{it.invoice.invoice_number}</td>
                  <td>{shortVendor(it.invoice.vendor_raw)}</td>
                  <td className="num"><b className="missing">{gbp(it.discount!.savings)}</b></td>
                  <td className="num">{Math.abs(it.discount!.days_left)}d ago</td>
                </tr>
              ))}
              {lost.length === 0 && <tr><td colSpan={4} className="hint">Nothing missed — approvals kept up this week.</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
