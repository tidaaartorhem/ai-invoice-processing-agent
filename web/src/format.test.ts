import { describe, expect, it } from 'vitest';
import { actionLabel, gbp, pct, shortVendor } from './format';

describe('format', () => {
  it('formats GBP money', () => {
    expect(gbp(4161.06)).toBe('£4,161.06');
    expect(gbp(null)).toBe('—');
    expect(gbp(0)).toBe('£0.00');
  });

  it('formats percents', () => {
    expect(pct(0.02)).toBe('2.0%');
    expect(pct(-0.5, 0)).toBe('-50%');
  });

  it('labels actions', () => {
    expect(actionLabel('approve')).toBe('Approve');
    expect(actionLabel('needs_review')).toBe('Needs review');
    expect(actionLabel('blocked')).toBe('Blocked');
  });

  it('shortens vendor names', () => {
    expect(shortVendor('Vendor account 12536 (France)')).toBe('Acct 12536 · France');
    expect(shortVendor('No account on file')).toBe('No account');
  });
});
