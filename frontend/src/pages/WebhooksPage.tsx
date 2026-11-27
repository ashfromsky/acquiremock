import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation } from '@tanstack/react-query';
import { RefreshCw, RotateCw } from 'lucide-react';
import { AppLayout } from '../layouts/AppLayout';
import { Button, ButtonLink } from '../components/ui/Button';
import { Input, Textarea } from '../components/ui/Input';
import { CopyButton } from '../components/ui/CopyButton';
import { StatusBadge } from '../components/ui/StatusBadge';
import { EmptyState, ErrorState, LoadingState } from '../components/ui/StateBlocks';
import { verifyWebhookSignature } from '../api/webhooks';
import { useConsoleWebhooks, useRetryWebhook } from '../hooks/useConsoleData';
import { webhookVerifySchema, type WebhookVerifyFormValues } from '../schemas/forms';
import { useToastStore } from '../store/toastStore';
import { formatDateTime, formatShortId, prettyJson } from '../utils/format';
import { handleTabListKeyDown } from '../utils/tablist';
import type { WebhookLogRecord } from '../types/api';
import styles from './WebhooksPage.module.css';

type FilterStatus = 'all' | 'succeeded' | 'failed';
type PageTab = 'logs' | 'verifier';
const PAGE_TABS: readonly PageTab[] = ['logs', 'verifier'];
const FILTER_TABS: readonly FilterStatus[] = ['all', 'succeeded', 'failed'];

export function WebhooksPage() {
  const [pageTab, setPageTab] = useState<PageTab>('logs');
  const [statusFilter, setStatusFilter] = useState<FilterStatus>('all');
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [verifyResult, setVerifyResult] = useState<boolean | null>(null);
  const [verifyError, setVerifyError] = useState<string | null>(null);
  const pushToast = useToastStore((s) => s.push);

  const successParam =
    statusFilter === 'succeeded' ? true : statusFilter === 'failed' ? false : null;

  const webhooksQuery = useConsoleWebhooks({
    success: successParam,
    limit: 50,
    offset: 0,
  });

  const retryMutation = useRetryWebhook();

  const {
    register,
    handleSubmit,
    setValue,
    formState: { errors },
  } = useForm<WebhookVerifyFormValues>({
    resolver: zodResolver(webhookVerifySchema),
    defaultValues: {
      payload: JSON.stringify(
        {
          payment_id: '550e8400-e29b-41d4-a716-446655440000',
          reference: 'ORDER-1042',
          amount: 25000,
          status: 'paid',
          timestamp: '2026-11-27T12:00:00',
          card_mask: '**** 4444',
        },
        null,
        2,
      ),
      signature: '',
    },
  });

  const verifyMutation = useMutation({
    mutationFn: ({ payload, signature }: { payload: Record<string, unknown>; signature: string }) =>
      verifyWebhookSignature(payload, signature),
    onSuccess: (res) => {
      setVerifyResult(res.valid);
      setVerifyError(null);
    },
    onError: (err) => {
      setVerifyResult(null);
      setVerifyError(err instanceof Error ? err.message : 'Verification request failed');
    },
  });

  function onVerifySubmit(values: WebhookVerifyFormValues) {
    setVerifyResult(null);
    setVerifyError(null);
    let parsed: unknown;
    try {
      parsed = JSON.parse(values.payload);
    } catch {
      setVerifyError('Payload must be valid JSON.');
      return;
    }
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      setVerifyError('Payload must be a JSON object.');
      return;
    }
    verifyMutation.mutate({
      payload: parsed as Record<string, unknown>,
      signature: values.signature.trim(),
    });
  }

  async function handleRetry(paymentId: string) {
    try {
      const res = await retryMutation.mutateAsync(paymentId);
      if (res.success) {
        pushToast(`Webhook delivered for ${formatShortId(paymentId)}.`, 'success');
      } else {
        pushToast('Webhook retry failed. Check attempt details.', 'error');
      }
    } catch (err) {
      pushToast(err instanceof Error ? err.message : 'Retry request failed', 'error');
    }
  }

  function loadIntoVerifier(log: WebhookLogRecord) {
    setValue('payload', prettyJson(log.payload));
    setValue('signature', log.signature);
    setVerifyResult(null);
    setVerifyError(null);
    setPageTab('verifier');
  }

  return (
    <AppLayout
      title="Webhooks"
      subtitle="Review signed webhook delivery attempts, retry failed callbacks, and verify X-Signature digests against your server secret."
      breadcrumbs={[{ label: 'Workspace', to: '/app/overview' }, { label: 'Webhooks' }]}
    >
      <div className={styles.topTabs} role="tablist" aria-label="Webhook tools">
        <button
          type="button"
          role="tab"
          tabIndex={pageTab === 'logs' ? 0 : -1}
          aria-selected={pageTab === 'logs'}
          className={`${styles.topTab} ${pageTab === 'logs' ? styles.topTabActive : ''}`}
          onClick={() => setPageTab('logs')}
          onKeyDown={(e) => handleTabListKeyDown(e, PAGE_TABS, pageTab, setPageTab)}
        >
          Delivery history
        </button>
        <button
          type="button"
          role="tab"
          tabIndex={pageTab === 'verifier' ? 0 : -1}
          aria-selected={pageTab === 'verifier'}
          className={`${styles.topTab} ${pageTab === 'verifier' ? styles.topTabActive : ''}`}
          onClick={() => setPageTab('verifier')}
          onKeyDown={(e) => handleTabListKeyDown(e, PAGE_TABS, pageTab, setPageTab)}
        >
          Signature verifier
        </button>
      </div>

      {pageTab === 'logs' ? (
        <div className={styles.logsView}>
          <div className={styles.toolbar}>
            <div className={styles.filterGroup} role="tablist" aria-label="Filter webhook deliveries">
              {FILTER_TABS.map((filter) => (
                <button
                  key={filter}
                  type="button"
                  role="tab"
                  tabIndex={statusFilter === filter ? 0 : -1}
                  aria-selected={statusFilter === filter}
                  className={`${styles.filterBtn} ${statusFilter === filter ? styles.filterActive : ''}`}
                  onClick={() => setStatusFilter(filter)}
                  onKeyDown={(e) => handleTabListKeyDown(e, FILTER_TABS, statusFilter, setStatusFilter)}
                >
                  {filter === 'all'
                    ? `All (${webhooksQuery.data?.summary.total ?? 0})`
                    : filter === 'succeeded'
                      ? `Succeeded (${webhooksQuery.data?.summary.succeeded ?? 0})`
                      : `Failed (${webhooksQuery.data?.summary.failed ?? 0})`}
                </button>
              ))}
            </div>

            <Button
              variant="secondary"
              size="sm"
              onClick={() => void webhooksQuery.refetch()}
              loading={webhooksQuery.isFetching && !webhooksQuery.isLoading}
            >
              <RefreshCw size={14} strokeWidth={1.75} />
              <span>Refresh</span>
            </Button>
          </div>

          {webhooksQuery.isLoading ? (
            <LoadingState label="Loading webhook delivery logs" />
          ) : webhooksQuery.isError ? (
            <ErrorState
              title="Could not load webhook logs"
              message={webhooksQuery.error.message}
              onRetry={() => void webhooksQuery.refetch()}
            />
          ) : webhooksQuery.data && webhooksQuery.data.items.length === 0 ? (
            <EmptyState
              title={
                statusFilter === 'all'
                  ? 'No webhook deliveries logged yet'
                  : `No ${statusFilter} webhook deliveries`
              }
              description={
                statusFilter === 'all'
                  ? 'Complete a payment or trigger a manual retry from any payment detail page to inspect webhook logs here.'
                  : 'Switch the status filter to inspect other webhook delivery attempts.'
              }
              action={
                statusFilter === 'all' ? (
                  <ButtonLink to="/app/testing" variant="primary" size="sm">
                    Create test payment
                  </ButtonLink>
                ) : (
                  <Button variant="secondary" size="sm" onClick={() => setStatusFilter('all')}>
                    Show all logs
                  </Button>
                )
              }
            />
          ) : webhooksQuery.data ? (
            <div className={styles.logList}>
              {webhooksQuery.data.items.map((log) => {
                const expanded = expandedId === log.id;
                return (
                  <div key={log.id} className={styles.logCard}>
                    <div className={styles.logSummary}>
                      <div className={styles.logMeta}>
                        <StatusBadge status={log.success ? 'success' : 'failed'} />
                        {log.trigger ? <StatusBadge status={log.trigger} /> : null}
                        <Link to={`/app/payments/${log.payment_id}`} className={styles.paymentLink}>
                          {formatShortId(log.payment_id)}
                        </Link>
                        <span className={`${styles.attemptBadge} mono-num`}>
                          Attempt #{log.attempt_number}
                        </span>
                        <span className={`${styles.httpStatus} mono-num`}>
                          {log.response_status
                            ? `HTTP ${log.response_status}`
                            : log.error_message || 'Request failed'}
                        </span>
                      </div>

                      <div className={styles.logActions}>
                        <span className={styles.logDate}>{formatDateTime(log.created_at)}</span>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => loadIntoVerifier(log)}
                        >
                          Verify signature
                        </Button>
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() => void handleRetry(log.payment_id)}
                          loading={retryMutation.isPending && retryMutation.variables === log.payment_id}
                        >
                          <RotateCw size={13} strokeWidth={1.75} />
                          <span>Retry</span>
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setExpandedId(expanded ? null : log.id)}
                        >
                          {expanded ? 'Collapse' : 'Inspect'}
                        </Button>
                      </div>
                    </div>

                    <div className={`${styles.targetUrl} mono-num`}>{log.webhook_url}</div>

                    {expanded ? (
                      <div className={styles.inspector}>
                        <div className={styles.inspectorSection}>
                          <div className={styles.inspectorHead}>
                            <span>X-Signature</span>
                            <CopyButton value={log.signature} compact />
                          </div>
                          <pre className={styles.pre}>{log.signature}</pre>
                        </div>
                        <div className={styles.inspectorSection}>
                          <div className={styles.inspectorHead}>
                            <span>Payload</span>
                            <CopyButton value={log.payload} compact />
                          </div>
                          <pre className={styles.pre}>{prettyJson(log.payload)}</pre>
                        </div>
                        {log.response_body ? (
                          <div className={styles.inspectorSection}>
                            <div className={styles.inspectorHead}>
                              <span>Response body</span>
                            </div>
                            <pre className={styles.pre}>{log.response_body}</pre>
                          </div>
                        ) : null}
                      </div>
                    ) : null}
                  </div>
                );
              })}
            </div>
          ) : null}
        </div>
      ) : (
        <div className={styles.verifierGrid}>
          <section className={styles.verifierPanel}>
            <h2 className={styles.panelTitle}>Verify X-Signature against server secret</h2>
            <p className={styles.panelDesc}>
              Calls POST /webhooks/verify with the JSON object and X-Signature header. Keys are sorted with compact separators before HMAC-SHA256 hashing.
            </p>

            <form className={styles.verifyForm} onSubmit={handleSubmit(onVerifySubmit)} noValidate>
              <Textarea
                label="Webhook JSON payload"
                rows={9}
                error={errors.payload?.message}
                {...register('payload')}
              />

              <Input
                label="X-Signature header (hex digest)"
                type="text"
                placeholder="Paste 64-character HMAC-SHA256 hex digest"
                error={errors.signature?.message}
                {...register('signature')}
              />

              {verifyError ? (
                <div className={styles.verifyError} role="alert">
                  {verifyError}
                </div>
              ) : null}

              {verifyResult !== null ? (
                <div
                  className={verifyResult ? styles.verifyPass : styles.verifyFail}
                  role="status"
                >
                  {verifyResult
                    ? 'Signature is valid and matches this server WEBHOOK_SECRET.'
                    : 'Signature mismatch. Check key sorting, compact formatting, or WEBHOOK_SECRET.'}
                </div>
              ) : null}

              <Button type="submit" variant="primary" loading={verifyMutation.isPending}>
                Verify signature
              </Button>
            </form>
          </section>

          <aside className={styles.verifierPanel}>
            <h2 className={styles.panelTitle}>Canonical verification rule</h2>
            <p className={styles.panelDesc}>
              Your webhook receiver must serialize the JSON object with alphabetically sorted keys and no whitespace after colons or commas.
            </p>
            <pre className={styles.darkCode}>{`message = json.dumps(payload, sort_keys=True, separators=(",", ":"))
expected = hmac.new(
    WEBHOOK_SECRET.encode(),
    message.encode(),
    hashlib.sha256,
).hexdigest()
is_valid = hmac.compare_digest(expected, signature)`}</pre>
          </aside>
        </div>
      )}
    </AppLayout>
  );
}
