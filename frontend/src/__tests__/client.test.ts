import { afterEach, describe, expect, it, vi } from 'vitest';
import { ADMIN_UNAUTHORIZED_EVENT, ApiError, apiFetch } from '../api/client';

describe('apiFetch', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    document.cookie = 'admin_csrf=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/';
  });

  it('attaches X-CSRF-Token from admin_csrf cookie on mutating requests', async () => {
    document.cookie = 'admin_csrf=test-csrf-123; path=/';
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ status: 'ok' }), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      }),
    );

    await apiFetch('/api/console/webhooks/p-1/retry', { method: 'POST' });

    expect(fetchSpy).toHaveBeenCalledTimes(1);
    const [, init] = fetchSpy.mock.calls[0];
    const headers = init?.headers as Headers;
    expect(headers.get('X-CSRF-Token')).toBe('test-csrf-123');
    expect(init?.credentials).toBe('same-origin');
  });

  it('parses structured PaymentError responses and emits unauthorized event on 401 console call', async () => {
    const onUnauthorized = vi.fn();
    window.addEventListener(ADMIN_UNAUTHORIZED_EVENT, onUnauthorized);

    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({
          error: 'UNAUTHORIZED',
          message: 'Administrator authentication required',
          payment_id: null,
        }),
        {
          status: 401,
          headers: { 'content-type': 'application/json' },
        },
      ),
    );

    await expect(apiFetch('/api/console/overview')).rejects.toMatchObject({
      name: 'ApiError',
      status: 401,
      code: 'UNAUTHORIZED',
      message: 'Administrator authentication required',
    } satisfies Partial<ApiError>);

    expect(onUnauthorized).toHaveBeenCalledTimes(1);
    window.removeEventListener(ADMIN_UNAUTHORIZED_EVENT, onUnauthorized);
  });

  it('parses FastAPI validation error arrays', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({
          detail: [{ loc: ['body', 'amount'], msg: 'Input should be greater than 0' }],
        }),
        {
          status: 422,
          headers: { 'content-type': 'application/json' },
        },
      ),
    );

    await expect(apiFetch('/api/create-invoice', { method: 'POST', body: '{}' })).rejects.toMatchObject({
      status: 422,
      code: 'VALIDATION_ERROR',
      message: 'amount: Input should be greater than 0',
    });
  });
});
