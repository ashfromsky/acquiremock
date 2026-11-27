import { apiFetch } from './client';
import type {
  ConsoleConfig,
  ConsoleOverviewResponse,
  ConsoleWebhooksResponse,
  HealthResponse,
  PaginatedPaymentsResponse,
  PaymentDetailResponse,
  RetryWebhookResponse,
} from '../types/api';

export function fetchHealth(): Promise<HealthResponse> {
  return apiFetch<HealthResponse>('/health');
}

export function fetchConsoleConfig(): Promise<ConsoleConfig> {
  return apiFetch<ConsoleConfig>('/api/console/config');
}

export function fetchConsoleOverview(): Promise<ConsoleOverviewResponse> {
  return apiFetch<ConsoleOverviewResponse>('/api/console/overview');
}

export function fetchConsolePayments(params: {
  status?: string;
  q?: string;
  limit?: number;
  offset?: number;
}): Promise<PaginatedPaymentsResponse> {
  const search = new URLSearchParams();
  if (params.status && params.status !== 'all') search.set('status', params.status);
  if (params.q?.trim()) search.set('q', params.q.trim());
  if (params.limit !== undefined) search.set('limit', String(params.limit));
  if (params.offset !== undefined) search.set('offset', String(params.offset));
  const query = search.toString();
  return apiFetch<PaginatedPaymentsResponse>(`/api/console/payments${query ? `?${query}` : ''}`);
}

export function fetchConsolePaymentDetail(paymentId: string): Promise<PaymentDetailResponse> {
  return apiFetch<PaymentDetailResponse>(`/api/console/payments/${encodeURIComponent(paymentId)}`);
}

export function fetchConsoleWebhooks(params: {
  success?: boolean | null;
  payment_id?: string;
  limit?: number;
  offset?: number;
}): Promise<ConsoleWebhooksResponse> {
  const search = new URLSearchParams();
  if (params.success !== undefined && params.success !== null) {
    search.set('success', String(params.success));
  }
  if (params.payment_id?.trim()) search.set('payment_id', params.payment_id.trim());
  if (params.limit !== undefined) search.set('limit', String(params.limit));
  if (params.offset !== undefined) search.set('offset', String(params.offset));
  const query = search.toString();
  return apiFetch<ConsoleWebhooksResponse>(`/api/console/webhooks${query ? `?${query}` : ''}`);
}

export function retryWebhookDelivery(paymentId: string): Promise<RetryWebhookResponse> {
  return apiFetch<RetryWebhookResponse>(
    `/api/console/webhooks/${encodeURIComponent(paymentId)}/retry`,
    { method: 'POST' },
  );
}
