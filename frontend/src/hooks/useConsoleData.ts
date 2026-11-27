import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  fetchConsoleConfig,
  fetchConsoleOverview,
  fetchConsolePaymentDetail,
  fetchConsolePayments,
  fetchConsoleWebhooks,
  fetchHealth,
  retryWebhookDelivery,
} from '../api/console';

export function useHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: fetchHealth,
    refetchInterval: 30000,
    retry: 1,
  });
}

export function useConsoleConfig() {
  return useQuery({
    queryKey: ['console', 'config'],
    queryFn: fetchConsoleConfig,
    staleTime: 60000,
  });
}

export function useConsoleOverview() {
  return useQuery({
    queryKey: ['console', 'overview'],
    queryFn: fetchConsoleOverview,
  });
}

export function useConsolePayments(params: {
  status?: string;
  q?: string;
  limit?: number;
  offset?: number;
}) {
  return useQuery({
    queryKey: ['console', 'payments', params],
    queryFn: () => fetchConsolePayments(params),
  });
}

export function useConsolePaymentDetail(paymentId: string) {
  return useQuery({
    queryKey: ['console', 'payment', paymentId],
    queryFn: () => fetchConsolePaymentDetail(paymentId),
    enabled: Boolean(paymentId),
  });
}

export function useConsoleWebhooks(params: {
  success?: boolean | null;
  payment_id?: string;
  limit?: number;
  offset?: number;
}) {
  return useQuery({
    queryKey: ['console', 'webhooks', params],
    queryFn: () => fetchConsoleWebhooks(params),
  });
}

export function useRetryWebhook() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (paymentId: string) => retryWebhookDelivery(paymentId),
    onSuccess: (_data, paymentId) => {
      void queryClient.invalidateQueries({ queryKey: ['console', 'payment', paymentId] });
      void queryClient.invalidateQueries({ queryKey: ['console', 'webhooks'] });
      void queryClient.invalidateQueries({ queryKey: ['console', 'overview'] });
      void queryClient.invalidateQueries({ queryKey: ['console', 'payments'] });
    },
  });
}
