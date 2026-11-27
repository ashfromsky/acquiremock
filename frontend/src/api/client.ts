export class ApiError extends Error {
  status: number;
  code: string;
  paymentId?: string | null;

  constructor(status: number, message: string, code = 'API_ERROR', paymentId?: string | null) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.paymentId = paymentId;
  }
}

interface FastApiErrorShape {
  detail?: string | Array<{ loc?: Array<string | number>; msg?: string }>;
  message?: string;
  error?: string;
  payment_id?: string | null;
}

function extractErrorMessage(body: unknown, fallbackStatus: number): {
  message: string;
  code: string;
  paymentId?: string | null;
} {
  if (!body || typeof body !== 'object') {
    return { message: `Request failed with status ${fallbackStatus}`, code: 'HTTP_ERROR' };
  }

  const parsed = body as FastApiErrorShape;

  if (typeof parsed.message === 'string' && parsed.message) {
    return {
      message: parsed.message,
      code: parsed.error || 'PAYMENT_ERROR',
      paymentId: parsed.payment_id,
    };
  }

  if (typeof parsed.detail === 'string' && parsed.detail) {
    return { message: parsed.detail, code: parsed.error || 'REQUEST_ERROR' };
  }

  if (Array.isArray(parsed.detail) && parsed.detail.length > 0) {
    const first = parsed.detail[0];
    const field = first?.loc ? first.loc.filter((part) => part !== 'body').join('.') : '';
    const msg = first?.msg || 'Validation error';
    return {
      message: field ? `${field}: ${msg}` : msg,
      code: 'VALIDATION_ERROR',
    };
  }

  return { message: `Request failed with status ${fallbackStatus}`, code: 'HTTP_ERROR' };
}

export async function apiFetch<T>(url: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (init?.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  const response = await fetch(url, {
    ...init,
    headers,
    credentials: 'same-origin',
  });

  const contentType = response.headers.get('content-type') || '';
  const isJson = contentType.includes('application/json');
  const data: unknown = isJson ? await response.json().catch(() => null) : await response.text().catch(() => null);

  if (!response.ok) {
    const { message, code, paymentId } = extractErrorMessage(data, response.status);
    throw new ApiError(response.status, message, code, paymentId);
  }

  return data as T;
}
