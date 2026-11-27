import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ErrorBoundary } from '../components/ErrorBoundary';
import { ConfirmDialog } from '../components/ui/ConfirmDialog';
import { PaymentDetailPage } from '../pages/PaymentDetailPage';
import { TestingPage } from '../pages/TestingPage';

function makeWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return { queryClient };
}

describe('console interactions and UI resilience', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('validates and submits create-invoice form in TestingPage with minor-unit presets', async () => {
    const user = userEvent.setup();
    const { queryClient } = makeWrapper();

    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = String(input);
      if (url === '/api/admin/session') {
        return new Response(
          JSON.stringify({ authenticated: true, username: 'admin', csrf_token: 'c', expires_at: null, configured: true }),
          { status: 200, headers: { 'content-type': 'application/json' } },
        );
      }
      if (url === '/api/console/config') {
        return new Response(
          JSON.stringify({
            version: '2.0.0',
            base_url: 'http://localhost:8000',
            currency_code: 'USD',
            currency_symbol: '$',
            currency_decimals: 2,
            smtp_enabled: false,
            allow_local_webhooks: false,
            payment_ttl_minutes: 15,
            max_webhook_attempts: 5,
          }),
          { status: 200, headers: { 'content-type': 'application/json' } },
        );
      }
      if (url === '/api/create-invoice') {
        return new Response(
          JSON.stringify({ pageUrl: 'http://localhost:8000/checkout/pay-created-1' }),
          { status: 200, headers: { 'content-type': 'application/json' } },
        );
      }
      return new Response('{}', { status: 404 });
    });

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={['/app/testing']}>
          <TestingPage />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    expect(await screen.findByRole('button', { name: '$250.00' })).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Create invoice' }));

    expect(await screen.findByText('http://localhost:8000/checkout/pay-created-1')).toBeInTheDocument();
  });

  it('displays formatted minor-unit amount and disables webhook retry when ineligible', async () => {
    const { queryClient } = makeWrapper();

    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = String(input);
      if (url === '/api/admin/session') {
        return new Response(
          JSON.stringify({ authenticated: true, username: 'admin', csrf_token: 'c', expires_at: null, configured: true }),
          { status: 200, headers: { 'content-type': 'application/json' } },
        );
      }
      if (url === '/api/console/config') {
        return new Response(
          JSON.stringify({
            version: '2.0.0',
            base_url: 'http://localhost:8000',
            currency_code: 'USD',
            currency_symbol: '$',
            currency_decimals: 2,
            smtp_enabled: false,
            allow_local_webhooks: false,
            payment_ttl_minutes: 15,
            max_webhook_attempts: 5,
          }),
          { status: 200, headers: { 'content-type': 'application/json' } },
        );
      }
      if (url === '/api/console/payments/pay-123') {
        return new Response(
          JSON.stringify({
            id: 'pay-123',
            amount: 25000,
            reference: 'ORD-250',
            status: 'paid',
            card_mask: '**** 4444',
            webhook_url: 'https://example.com/hook',
            redirect_url: 'https://example.com/ok',
            webhook_status: 'success',
            webhook_delivery_state: 'succeeded',
            webhook_can_retry: false,
            webhook_attempts: 1,
            webhook_last_attempt: '2026-11-27T10:00:00',
            webhook_next_attempt_at: null,
            error_code: null,
            error_message: null,
            created_at: '2026-11-27T10:00:00',
            updated_at: '2026-11-27T10:00:00',
            expires_at: '2026-11-27T10:15:00',
            paid_at: '2026-11-27T10:01:00',
            webhook_logs: [],
          }),
          { status: 200, headers: { 'content-type': 'application/json' } },
        );
      }
      return new Response('{}', { status: 404 });
    });

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={['/app/payments/pay-123']}>
          <Routes>
            <Route path="/app/payments/:paymentId" element={<PaymentDetailPage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );

    await waitFor(() => {
      expect(screen.getByText('$250.00')).toBeInTheDocument();
    });
    expect(screen.getByRole('button', { name: 'Send webhook now' })).toBeDisabled();
  });

  it('closes ConfirmDialog on Escape and renders ErrorBoundary fallback on crash', async () => {
    const user = userEvent.setup();
    const onCancel = vi.fn();

    render(
      <ConfirmDialog
        open
        title="Confirm action"
        description="Delete item?"
        onCancel={onCancel}
        onConfirm={vi.fn()}
      />,
    );

    await user.keyboard('{Escape}');
    expect(onCancel).toHaveBeenCalledTimes(1);

    function Boom(): null {
      throw new Error('Test render crash');
    }
    const errSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    render(
      <ErrorBoundary>
        <Boom />
      </ErrorBoundary>,
    );
    expect(screen.getByText('Something went wrong')).toBeInTheDocument();
    expect(screen.getByText('Test render crash')).toBeInTheDocument();
    errSpy.mockRestore();
  });
});
