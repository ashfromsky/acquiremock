import { apiFetch } from './client';
import type { VerifyWebhookResponse } from '../types/api';

export function verifyWebhookSignature(
  payload: Record<string, unknown>,
  signature: string,
): Promise<VerifyWebhookResponse> {
  return apiFetch<VerifyWebhookResponse>('/webhooks/verify', {
    method: 'POST',
    headers: {
      'X-Signature': signature,
    },
    body: JSON.stringify(payload),
  });
}
