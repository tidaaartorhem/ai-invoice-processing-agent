export interface LineItem {
  description: string;
  qty: number;
  unit_price: number;
  amount: number;
}

export interface InvoiceSummary {
  invoice_id: string;
  vendor_raw: string;
  vendor_key: string;
  invoice_number: string;
  invoice_date: string | null;
  currency: string;
  total: number | null;
  n_lines: number;
  lines: LineItem[];
  source: string;
}

export interface LineMatch extends LineItem {
  po_unit_price?: number;
  price_variance?: number;
  po_status?: string;
  received_qty?: number;
  grn_status?: string;
}

export interface MatchInfo {
  po_number: string | null;
  grn_numbers: string[];
  way: string;
  passed: boolean;
  exceptions: string[];
  exception_codes: string[];
  line_matches: LineMatch[];
}

export interface GLSuggestion {
  gl_code: string;
  gl_name: string;
  confidence: number;
  reason: string;
}

export interface DiscountInfo {
  rate: number;
  discount_days: number;
  deadline: string;
  days_left: number;
  savings: number;
  annualized_rate: number;
  capturable: boolean;
}

export type ActionKind = 'approve' | 'needs_review' | 'blocked';

export interface QueueItem {
  invoice: InvoiceSummary;
  match: MatchInfo;
  gl_suggestions: GLSuggestion[];
  discount: DiscountInfo | null;
  recommendation: {
    action: ActionKind;
    priority: number;
    reasons: string[];
  };
}

export interface QueueBundle {
  review_date: string;
  window: [string, string];
  queue_size: number;
  shipped: number;
  items: QueueItem[];
}

export interface DuplicatePair {
  tier: string;
  reason: string;
  in_review_week: boolean;
  a: { invoice_id: string; invoice_number: string; vendor_raw: string; invoice_date: string | null; total: number | null };
  b: { invoice_id: string; invoice_number: string; vendor_raw: string; invoice_date: string | null; total: number | null };
}

export interface DuplicatesBundle {
  scanned_invoices: number;
  pairs: DuplicatePair[];
  pairs_touching_week: number;
}

export interface AnalyticsBundle {
  corpus_invoices: number;
  window_invoices: number;
  window_spend: number;
  currency: string;
  actions: Record<string, number>;
  value_by_action: Record<string, number>;
  exceptions: Record<string, number>;
  discount_capturable: number;
  discount_lost: number;
  top_vendors: { vendor: string; spend: number }[];
  no_po_under_50: { count: number; spend: number };
  pos_seeded: number;
  grns_seeded: number;
}

export interface MetaBundle {
  project: string;
  review_date: string;
  window: [string, string];
  corpus: string;
  company_records: string;
  pipeline: string;
  generated_by: string;
}

export interface PasteSample {
  title: string;
  text: string;
  fields: Record<string, unknown>;
  missing: string[];
  result?: QueueItem;
}
