import { describe, expect, it } from 'vitest';
import { formatAmount, getCurrencyDecimals } from '../utils/format';

describe('formatAmount', () => {
  it('formats 2-decimal currencies from integer minor units', () => {
    expect(formatAmount(25000, 'USD', '$')).toBe('$250.00');
    expect(formatAmount(50, 'USD', '$')).toBe('$0.50');
    expect(formatAmount(1000000, 'EUR', '€')).toBe('€10,000.00');
    expect(formatAmount(25000, 'UAH', '₴')).toBe('250.00 ₴');
  });

  it('formats 0-decimal and 3-decimal currencies accurately', () => {
    expect(getCurrencyDecimals('JPY')).toBe(0);
    expect(formatAmount(500, 'JPY', '¥')).toBe('¥500');
    expect(getCurrencyDecimals('KWD')).toBe(3);
    expect(formatAmount(12345, 'KWD', 'KWD')).toBe('12.345 KWD');
    expect(formatAmount(5, 'BHD', 'BHD')).toBe('0.005 BHD');
  });

  it('handles negative and non-finite edge values safely', () => {
    expect(formatAmount(-1050, 'USD', '$')).toBe('-$10.50');
    expect(formatAmount(Number.NaN, 'USD', '$')).toBe('$0.00');
  });
});
