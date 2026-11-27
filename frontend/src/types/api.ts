export type PaymentStatus =
  | 'pending'
  | 'waiting_for_otp'
  | 'paid'
  | 'failed'
  | 'expired'
  | 'refunded';

export interface HealthResponse {
  status: string;
  timestamp: string;
  version: string;
  currency: string;
}

export interface ConsoleConfig {
  version: string;
  base_url: string;
  currency_code: string;
  currency_symbol: string;
  smtp_enabled: boolean;
  allow_local_webhooks: boolean;
  payment_ttl_minutes: number;
  max_webhook_attempts: number;
}

export interface PaymentRecord {
  id: string;
  amount: number;
  reference: string;
  status: PaymentStatus | string;
  card_mask: string | null;
  webhook_url: string;
  redirect_url: string;
  webhook_status: string | null;
  webhook_attempts: number;
  webhook_last_attempt: string | null;
  error_code: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
  expires_at: string;
  paid_at: string | null;
}

export interface WebhookLogRecord {
  id: number;
  payment_id: string;
  webhook_url: string;
  payload: string;
  response_status: number | null;
  response_body: string | null;
  signature: string;
  attempt_number: number;
  success: boolean;
  error_message: string | null;
  created_at: string;
}

export interface PaymentDetailResponse extends PaymentRecord {
  webhook_logs: WebhookLogRecord[];
}

export interface ConsoleOverviewResponse {
  payments: {
    total: number;
    paid: number;
    pending: number;
    waiting_for_otp: number;
    failed: number;
    expired: number;
    paid_volume: number;
  };
  webhooks: {
    total: number;
    succeeded: number;
    failed: number;
    success_rate: number | null;
  };
  recent_payments: PaymentRecord[];
}

export interface PaginatedPaymentsResponse {
  items: PaymentRecord[];
  total: number;
  limit: number;
  offset: number;
}

export interface ConsoleWebhooksResponse {
  items: WebhookLogRecord[];
  total: number;
  summary: {
    total: number;
    succeeded: number;
    failed: number;
  };
}

export interface RetryWebhookResponse {
  success: boolean;
  payment_id: string;
  webhook_status: string | null;
  webhook_attempts: number;
  latest_log: WebhookLogRecord | null;
}

export interface CreateInvoicePayload {
  amount: number;
  reference: string;
  webhookUrl: string;
  redirectUrl: string;
}

export interface CreateInvoiceResponse {
  pageUrl: string;
}

export interface AuthSessionResponse {
  authenticated: boolean;
  email: string | null;
}

export interface UserOperation {
  reference: string;
  amount: number;
  card_mask: string;
  date: string;
}

export interface SavedCard {
  id: number;
  mask: string;
  expiry: string;
}

export interface UserInfoResponse {
  operations: UserOperation[];
  cards: SavedCard[];
}

export interface VerifyWebhookResponse {
  valid: boolean;
}
