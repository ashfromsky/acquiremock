export function formatAmount(amount: number, symbol = '$'): string {
  const formatted = new Intl.NumberFormat('en-US', {
    maximumFractionDigits: 0,
  }).format(amount);
  return `${formatted} ${symbol}`;
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
