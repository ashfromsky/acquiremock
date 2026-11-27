import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ExternalLink, RotateCw } from 'lucide-react';
import { AppLayout } from '../layouts/AppLayout';
import { AnchorButton, Button } from '../components/ui/Button';
import { CopyButton } from '../components/ui/CopyButton';
import { StatusBadge } from '../components/ui/StatusBadge';
import { EmptyState, ErrorState, LoadingState } from '../components/ui/StateBlocks';
import {
  useConsoleConfig,
  useConsolePaymentDetail,
  useRetryWebhook,
} from '../hooks/useConsoleData';
import { useToastStore } from '../store/toastStore';
import { formatAmount, formatDateTime, prettyJson } from '../utils/format';
import styles from './PaymentDetailPage.module.css';

export function PaymentDetailPage() {
  const { paymentId = '' } = useParams();
  const [expandedLogId, setExpandedLogId] = useState<number | null>(null);
  const pushToast = useToastStore((s) => s.push);

  const configQuery = useConsoleConfig();
  const detailQuery = useConsolePaymentDetail(paymentId);
  const retryMutation = useRetryWebhook();

  const symbol = configQuery.data?.currency_symbol ?? '$';
  const currencyCode = configQuery.data?.currency_code ?? 'USD';
  const payment = detailQuery.data;
  const canRetryWebhook = payment?.webhook_can_retry ?? (
    payment?.status === 'paid' &&
    payment.webhook_status !== 'success' &&
    payment.webhook_attempts < (configQuery.data?.max_webhook_attempts ?? 5)
  );

  async function handleRetryWebhook() {
    if (!payment) return;
    try {
      const result = await retryMutation.mutateAsync(payment.id);
      if (result.success) {
        pushToast('Webhook delivered successfully.', 'success');
      } else {
        pushToast('Webhook delivery failed. Inspect the new attempt log below.', 'error');
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to retry webhook';
      pushToast(message, 'error');
    }
  }

  const contextualHref = payment
    ? payment.status === 'pending'
      ? `/checkout/${payment.id}`
      : payment.status === 'waiting_for_otp'
        ? `/otp/${payment.id}`
        : payment.status === 'paid'
          ? `/success/${payment.id}`
          : null
    : null;

  const contextualLabel = payment
    ? payment.status === 'pending'
      ? 'Open hosted checkout'
      : payment.status === 'waiting_for_otp'
        ? 'Open OTP verification'
        : payment.status === 'paid'
          ? 'Open success receipt'
          : null
    : null;

  return (
    <AppLayout
      title={payment ? payment.reference : 'Payment details'}
      subtitle={payment ? `Payment ID: ${payment.id}` : 'Loading payment record'}
      breadcrumbs={[
        { label: 'Workspace', to: '/app/overview' },
        { label: 'Payments', to: '/app/payments' },
        { label: payment ? payment.reference : paymentId.slice(0, 8) },
      ]}
      actions={
        contextualHref && contextualLabel ? (
          <AnchorButton
            href={contextualHref}
            target="_blank"
            rel="noreferrer"
            variant="secondary"
            size="sm"
          >
            <span>{contextualLabel}</span>
            <ExternalLink size={14} strokeWidth={1.75} />
          </AnchorButton>
        ) : undefined
      }
    >
      {detailQuery.isLoading ? (
        <LoadingState label="Loading payment details" />
      ) : detailQuery.isError ? (
        <ErrorState
          title="Could not load payment"
          message={detailQuery.error.message}
          onRetry={() => void detailQuery.refetch()}
        />
      ) : payment ? (
        <div className={styles.layout}>
          <section className={styles.summaryBar}>
            <div className={styles.summaryItem}>
              <span className={styles.summaryLabel}>Amount</span>
              <span className={`${styles.summaryBig} mono-num`}>
                {formatAmount(payment.amount, currencyCode, symbol)}
              </span>
            </div>
            <div className={styles.summaryItem}>
              <span className={styles.summaryLabel}>Lifecycle status</span>
              <div className={styles.badgeWrap}>
                <StatusBadge status={payment.status} />
              </div>
            </div>
            <div className={styles.summaryItem}>
              <span className={styles.summaryLabel}>Card mask</span>
              <span className={`${styles.summaryValue} mono-num`}>
                {payment.card_mask || 'Not entered'}
              </span>
            </div>
            <div className={styles.summaryItem}>
              <span className={styles.summaryLabel}>Payment ID</span>
              <div className={styles.copyRow}>
                <span className={`${styles.summaryMono} mono-num`}>{payment.id}</span>
                <CopyButton value={payment.id} compact />
              </div>
            </div>
          </section>

          {payment.error_code || payment.error_message ? (
            <div className={styles.errorBanner} role="alert">
              <strong>{payment.error_code || 'PAYMENT_ERROR'}</strong>
              <span>{payment.error_message}</span>
            </div>
          ) : null}

          <section className={styles.panel}>
            <h2 className={styles.panelTitle}>Metadata and endpoints</h2>
            <dl className={styles.detailsGrid}>
              <div className={styles.detailRow}>
                <dt>Created</dt>
                <dd>{formatDateTime(payment.created_at)}</dd>
              </div>
              <div className={styles.detailRow}>
                <dt>Expires</dt>
                <dd>{formatDateTime(payment.expires_at)}</dd>
              </div>
              <div className={styles.detailRow}>
                <dt>Paid at</dt>
                <dd>{formatDateTime(payment.paid_at)}</dd>
              </div>
              <div className={styles.detailRow}>
                <dt>Last updated</dt>
                <dd>{formatDateTime(payment.updated_at)}</dd>
              </div>
              <div className={styles.detailRowFull}>
                <dt>Webhook URL</dt>
                <dd className={styles.urlValue}>
                  <span className="mono-num">{payment.webhook_url}</span>
                  <CopyButton value={payment.webhook_url} compact />
                </dd>
              </div>
              <div className={styles.detailRowFull}>
                <dt>Redirect URL</dt>
                <dd className={styles.urlValue}>
                  <span className="mono-num">{payment.redirect_url}</span>
                  <CopyButton value={payment.redirect_url} compact />
                </dd>
              </div>
            </dl>
          </section>

          <section className={styles.panel}>
            <div className={styles.panelHead}>
              <div>
                <h2 className={styles.panelTitle}>Webhook delivery logs</h2>
                <p className={styles.panelSub}>
                  {payment.webhook_attempts} recorded {payment.webhook_attempts === 1 ? 'attempt' : 'attempts'} · State:{' '}
                  {payment.webhook_delivery_state || payment.webhook_status || 'never_attempted'}
                  {payment.webhook_next_attempt_at
                    ? ` · Next retry: ${formatDateTime(payment.webhook_next_attempt_at)}`
                    : ''}
                </p>
              </div>

              <Button
                variant="secondary"
                size="sm"
                onClick={() => void handleRetryWebhook()}
                loading={retryMutation.isPending}
                disabled={!canRetryWebhook}
                title={
                  canRetryWebhook
                    ? 'Send webhook delivery now'
                    : 'Manual retry is available only for paid payments with pending or failed webhooks below max attempts'
                }
              >
                <RotateCw size={14} strokeWidth={1.75} />
                <span>Send webhook now</span>
              </Button>
            </div>

            {payment.webhook_logs.length === 0 ? (
              <EmptyState
                title="No webhook deliveries logged yet"
                description="Webhooks are dispatched automatically when a payment succeeds, or you can trigger a delivery manually above."
              />
            ) : (
              <div className={styles.logList}>
                {payment.webhook_logs.map((log) => {
                  const expanded = expandedLogId === log.id;
                  return (
                    <div key={log.id} className={styles.logRow}>
                      <div className={styles.logMain}>
                        <div className={styles.logLeft}>
                          <span className={`${styles.attemptTag} mono-num`}>
                            Attempt #{log.attempt_number}
                          </span>
                          <StatusBadge status={log.success ? 'success' : 'failed'} />
                          {log.trigger ? <StatusBadge status={log.trigger} /> : null}
                          <span className={`${styles.httpCode} mono-num`}>
                            {log.response_status ? `HTTP ${log.response_status}` : log.error_message || 'No response'}
                          </span>
                        </div>
                        <div className={styles.logRight}>
                          <span className={styles.logTime}>{formatDateTime(log.created_at)}</span>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setExpandedLogId(expanded ? null : log.id)}
                          >
                            {expanded ? 'Hide payload' : 'Inspect'}
                          </Button>
                        </div>
                      </div>

                      {expanded ? (
                        <div className={styles.logInspector}>
                          <div className={styles.inspectorBlock}>
                            <div className={styles.inspectorLabel}>
                              <span>X-Signature</span>
                              <CopyButton value={log.signature} compact />
                            </div>
                            <pre className={styles.inspectorPre}>{log.signature}</pre>
                          </div>
                          <div className={styles.inspectorBlock}>
                            <div className={styles.inspectorLabel}>
                              <span>Payload JSON</span>
                              <CopyButton value={log.payload} compact />
                            </div>
                            <pre className={styles.inspectorPre}>{prettyJson(log.payload)}</pre>
                          </div>
                          {log.response_body ? (
                            <div className={styles.inspectorBlock}>
                              <div className={styles.inspectorLabel}>
                                <span>Response body</span>
                              </div>
                              <pre className={styles.inspectorPre}>{log.response_body}</pre>
                            </div>
                          ) : null}
                        </div>
                      ) : null}
                    </div>
                  );
                })}
              </div>
            )}
          </section>

          <div>
            <Link to="/app/payments" className={styles.backLink}>
              Back to all payments
            </Link>
          </div>
        </div>
      ) : null}
    </AppLayout>
  );
}
