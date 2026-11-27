const ZERO_DECIMAL_CURRENCIES = new Set([
  'BIF',
  'CLP',
  'DJF',
  'GNF',
  'ISK',
  'JPY',
  'KMF',
  'KRW',
  'PYG',
  'RWF',
  'UGX',
  'VND',
  'VUV',
  'XAF',
  'XOF',
  'XPF',
]);

const THREE_DECIMAL_CURRENCIES = new Set([
  'BHD',
  'IQD',
  'JOD',
  'KWD',
  'LYD',
  'OMR',
  'TND',
]);

const PREFIX_SYMBOLS = new Set(['$', '£', '€', '¥', '₹', '₩', '₪', '₫']);

export function getCurrencyDecimals(currencyCode = 'USD'): number {
  const code = currencyCode.trim().toUpperCase();
  if (ZERO_DECIMAL_CURRENCIES.has(code)) return 0;
  if (THREE_DECIMAL_CURRENCIES.has(code)) return 3;
  return 2;
}

export function formatAmount(
  amountMinor: number,
  currencyCode = 'USD',
  symbol = '$',
): string {
  const decimals = getCurrencyDecimals(currencyCode);
  const integerAmount = Math.trunc(Number.isFinite(amountMinor) ? amountMinor : 0);
  const sign = integerAmount < 0 ? '-' : '';
  const absValue = Math.abs(integerAmount);

  let numberStr: string;
  if (decimals === 0) {
    numberStr = new Intl.NumberFormat('en-US', {
      maximumFractionDigits: 0,
    }).format(absValue);
  } else {
    const divisor = 10 ** decimals;
    const whole = Math.floor(absValue / divisor);
    const frac = absValue % divisor;
    const wholeFormatted = new Intl.NumberFormat('en-US', {
      maximumFractionDigits: 0,
    }).format(whole);
    const fracFormatted = String(frac).padStart(decimals, '0');
    numberStr = `${wholeFormatted}.${fracFormatted}`;
  }

  if (PREFIX_SYMBOLS.has(symbol)) {
    return `${sign}${symbol}${numberStr}`;
  }
  return `${sign}${numberStr} ${symbol}`.trim();
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return 'Not yet';
  const normalized = iso.endsWith('Z') || iso.includes('+') ? iso : `${iso}Z`;
  const date = new Date(normalized);
  if (Number.isNaN(date.getTime())) return iso;
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).format(date);
}

export function formatShortId(id: string): string {
  if (id.length <= 12) return id;
  return `${id.slice(0, 8)}...${id.slice(-4)}`;
}

export function getRuntimeBaseUrl(): string {
  if (typeof document !== 'undefined') {
    const meta = document.querySelector('meta[name="acquiremock-base-url"]');
    const content = meta?.getAttribute('content');
    if (content) return content;
  }
  if (typeof window !== 'undefined') {
    return window.location.origin;
  }
  return 'http://localhost:8000';
}

export function extractPaymentIdFromUrl(pageUrl: string): string | null {
  try {
    const parsed = new URL(pageUrl);
    const parts = parsed.pathname.split('/').filter(Boolean);
    return parts.length > 0 ? parts[parts.length - 1] : null;
  } catch {
    const parts = pageUrl.split('/').filter(Boolean);
    return parts.length > 0 ? parts[parts.length - 1] : null;
  }
}

export function prettyJson(raw: string): string {
  try {
    return JSON.stringify(JSON.parse(raw), null, 2);
  } catch {
    return raw;
  }
}
