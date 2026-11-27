import { apiFetch } from './client';
import type { CreateInvoicePayload, CreateInvoiceResponse } from '../types/api';

export function createInvoice(payload: CreateInvoicePayload): Promise<CreateInvoiceResponse> {
  return apiFetch<CreateInvoiceResponse>('/api/create-invoice', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}
