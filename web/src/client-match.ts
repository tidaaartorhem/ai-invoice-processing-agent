/** Client-side invoice matching — TS port of services/match.py, gl.py,
 *  discounts.py and actions.py, so the paste-an-invoice tab works live in the
 *  browser against the shipped registers.json bundle. Same tolerances,
 *  same policy: nothing here pays anything. */

export interface RegLine { description: string; qty: number; unit_price: number; }
export interface RegPO { po_number: string; vendor_key: string; lines: RegLine[]; }
export interface RegGRN { grn_number: string; po_number: string; lines: RegLine[]; }
export interface Registers {
  terms: Record<string, string>;
  purchase_orders: RegPO[];
  goods_receipts: RegGRN[];
}

export interface PastedLine { description: string; qty: number; unit_price: number | null; }
export interface PastedInvoice {
  vendor_raw: string;
  vendor_key: string;
  invoice_number: string;
  invoice_date: string | null; // ISO
  currency: string;
  total: number | null;
  lines: PastedLine[];
  payment_terms: string;
}

const PRICE_TOL = 0.02;
const TOTAL_TOL = 1.0;

export function vendorKey(raw: string): string {
  return raw.toLowerCase()
    .replace(/\b(inc\.?|ltd\.?|llc|co\.?|corp\.?|corporation|limited|gmbh|s\.?a\.?|pvt\.?|plc)\b/gi, '')
    .replace(/[^a-z0-9 ]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function lineKey(d: string): string {
  return d.toLowerCase().split(/\s+/).join(' ');
}

const GL_TABLE: [string, string, string[]][] = [
  ['5000', 'Merchandise for Resale (COGS)', ['holder','lantern','mug','candle','decoration','gift','ribbon','ornament','t-light','tlight','hanger','coathanger','light','bottle','warmer','sticker','tag','card','wrap','bag','box','plate','stand','bank','cracker','chain kit','trinket','chandelier','sleigh','stocking','angel','star','heart','basket','frame','mirror','clock','vase','cushion','throw','apron','napkin','cutlery','doormat','plant','tool']],
  ['6000', 'Office Supplies', ['office','paper','toner','stationery','pen','ink','desk','notebook','printer','supplies']],
  ['6100', 'Software & SaaS', ['software','saas','subscription','license','cloud','hosting','api','seat','renewal']],
  ['6200', 'Utilities', ['electric','water','gas','internet','phone','utility','hydro','telecom','broadband']],
  ['6300', 'Rent & Facilities', ['rent','lease','facility','cleaning','maintenance','repair','hvac','plumbing']],
  ['6400', 'Marketing & Advertising', ['marketing','advertising','ads','seo','campaign','sponsor','printing','signage','design']],
  ['6500', 'Professional Services', ['consulting','legal','accounting','audit','attorney','advisor','service fee','professional']],
  ['6600', 'Travel & Meals', ['travel','flight','hotel','taxi','uber','meal','dinner','lunch','airfare','lodging','mileage']],
  ['6700', 'IT Equipment', ['laptop','monitor','keyboard','server','hardware','computer','equipment','cable','router']],
  ['6800', 'Insurance', ['insurance','premium','policy','coverage','liability']],
  ['6900', 'Shipping & Freight', ['shipping','freight','courier','delivery','postage','ups','fedex','dhl']],
];

export interface ClientGL { gl_code: string; gl_name: string; confidence: number; reason: string; }

export function suggestGL(lines: PastedLine[]): ClientGL[] {
  const total = lines.reduce((s, l) => s + Math.max((l.qty * (l.unit_price ?? 0)), 0), 0);
  if (total <= 0) return [];
  const out: ClientGL[] = [];
  for (const [code, name, kws] of GL_TABLE) {
    const hits = new Set<string>();
    let covered = 0;
    for (const l of lines) {
      const low = l.description.toLowerCase();
      const found = kws.filter((k) => low.includes(k));
      if (found.length > 0) { found.forEach((k) => hits.add(k)); covered += Math.max(l.qty * (l.unit_price ?? 0), 0); }
    }
    if (hits.size > 0) {
      const conf = covered / total;
      out.push({ gl_code: code, gl_name: name, confidence: Math.round(conf * 1000) / 1000,
        reason: `${Math.round(conf * 100)}% of invoice spend mentions ${[...hits].sort().join(', ')}.` });
    }
  }
  return out.sort((a, b) => b.confidence - a.confidence).slice(0, 2);
}

export interface ClientDiscount {
  rate: number; discount_days: number; deadline: string; days_left: number;
  savings: number; annualized_rate: number; capturable: boolean;
}

export function evalDiscount(invoiceDate: string | null, total: number | null, terms: string, reviewDate: string): ClientDiscount | null {
  const m = (terms || '').toLowerCase().match(/(\d+(?:\.\d+)?)\s*\/\s*(\d+)\s*net\s*\d+/);
  if (!m || !invoiceDate || total === null) return null;
  const rate = parseFloat(m[1]) / 100;
  const days = parseInt(m[2], 10);
  const deadline = new Date(invoiceDate + 'T00:00:00');
  deadline.setDate(deadline.getDate() + days);
  const review = new Date(reviewDate + 'T00:00:00');
  const daysLeft = Math.round((deadline.getTime() - review.getTime()) / 86400000);
  const apr = (rate / (1 - rate)) * (365 / Math.max(30 - days, 1));
  return {
    rate, discount_days: days, deadline: deadline.toISOString().slice(0, 10),
    days_left: daysLeft, savings: Math.round(total * rate * 100) / 100,
    annualized_rate: Math.round(apr * 1000) / 1000, capturable: daysLeft >= 0,
  };
}

export interface ClientRec {
  action: 'approve' | 'needs_review' | 'blocked';
  priority: number;
  reasons: string[];
  match: { po_number: string | null; way: string; passed: boolean; exceptions: string[] };
  gl: ClientGL[];
  discount: ClientDiscount | null;
  terms_used: string;
}

export function recommendPasted(inv: PastedInvoice, regs: Registers, reviewDate: string): ClientRec {
  const reasons: string[] = [];
  let action: ClientRec['action'] = 'approve';
  let priority = 10;
  const exceptions: string[] = [];
  let po_number: string | null = null;
  let way = 'none';

  const po = regs.purchase_orders.find((p) => p.vendor_key === inv.vendor_key) ?? null;
  const terms = inv.payment_terms || regs.terms[inv.vendor_key] || '';

  if (!po) {
    action = 'needs_review';
    exceptions.push('missing_po');
    reasons.push(`No purchase order on file for ${inv.vendor_raw} — cannot match.`);
    priority = Math.max(priority, 80);
  } else {
    po_number = po.po_number;
    const poLines: Record<string, RegLine> = {};
    po.lines.forEach((l) => { poLines[lineKey(l.description)] = l; });
    const grns = regs.goods_receipts.filter((g) => g.po_number === po.po_number);
    way = grns.length > 0 ? '3-way' : '2-way';

    for (const ln of inv.lines) {
      const key = lineKey(ln.description);
      const pl = poLines[key];
      if (!pl) {
        action = 'needs_review';
        exceptions.push('price_variance');
        reasons.push(`Line "${ln.description}" has no matching PO line.`);
        priority = Math.max(priority, 70);
        continue;
      }
      if (pl.unit_price && ln.unit_price !== null) {
        const v = (ln.unit_price - pl.unit_price) / pl.unit_price;
        if (Math.abs(v) > PRICE_TOL) {
          action = 'needs_review';
          exceptions.push('price_variance');
          reasons.push(`Price variance ${(v * 100).toFixed(1)}% on "${ln.description}" (invoiced ${ln.unit_price.toFixed(2)} vs PO ${pl.unit_price.toFixed(2)}).`);
          priority = Math.max(priority, 70);
        }
      }
      if (grns.length > 0) {
        let received = 0;
        grns.forEach((g) => g.lines.forEach((l) => { if (lineKey(l.description) === key) received += l.qty; }));
        if (received < ln.qty) {
          action = 'needs_review';
          exceptions.push('qty_not_received');
          reasons.push(`Invoiced qty ${ln.qty} of "${ln.description}" exceeds received qty ${received}.`);
          priority = Math.max(priority, 75);
        }
      }
    }
    if (grns.length === 0 && inv.lines.length > 0) {
      action = 'needs_review';
      exceptions.push('grn_missing');
      reasons.push('No goods receipt on file for this PO — 3-way match not possible.');
      priority = Math.max(priority, 50);
    }
    if (inv.total !== null && inv.lines.length > 0) {
      const footed = Math.round(inv.lines.reduce((s, l) => s + l.qty * (l.unit_price ?? 0), 0) * 100) / 100;
      if (Math.abs(inv.total - footed) > TOTAL_TOL) {
        action = 'needs_review';
        exceptions.push('total_mismatch');
        reasons.push(`Invoice total ${inv.total.toFixed(2)} does not foot to its line items (${footed.toFixed(2)}).`);
        priority = Math.max(priority, 85);
      }
    }
  }

  const gl = suggestGL(inv.lines);
  const discount = evalDiscount(inv.invoice_date, inv.total, terms, reviewDate);
  if (discount && discount.capturable && discount.days_left <= 5) {
    reasons.push(`Early-pay discount ${(discount.rate * 100).toFixed(0)}% expires in ${discount.days_left}d — worth £${discount.savings.toFixed(2)} (${(discount.annualized_rate * 100).toFixed(0)}% APR equivalent).`);
    priority = Math.max(priority, 60);
  } else if (discount && !discount.capturable) {
    reasons.push(`Early-pay discount ${(discount.rate * 100).toFixed(0)}% expired — £${discount.savings.toFixed(2)} lost.`);
    priority = Math.max(priority, 55);
  }

  if (action === 'approve' && reasons.length === 0) {
    reasons.push(`${way} match clean within tolerance. Ready to approve.`);
  }

  return { action, priority: Math.min(priority, 100), reasons,
    match: { po_number, way, passed: po !== null && exceptions.length === 0, exceptions },
    gl, discount, terms_used: terms };
}
