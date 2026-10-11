export function gbp(n: number | null | undefined): string {
  if (n === null || n === undefined || Number.isNaN(n)) return '—';
  return '£' + n.toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export function pct(x: number, digits = 1): string {
  return (x * 100).toFixed(digits) + '%';
}

export function actionLabel(a: string): string {
  return a === 'approve' ? 'Approve' : a === 'needs_review' ? 'Needs review' : 'Blocked';
}

export function shortVendor(vendorRaw: string): string {
  // "Vendor account 12536 (France)" -> "Acct 12536 · France"
  const m = vendorRaw.match(/Vendor account (\d+)\s*\(([^)]+)\)/i);
  if (m) return `Acct ${m[1]} · ${m[2]}`;
  if (/no account/i.test(vendorRaw)) return 'No account';
  return vendorRaw;
}
