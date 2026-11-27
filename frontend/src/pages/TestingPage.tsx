import { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { ExternalLink, RefreshCw } from 'lucide-react';
import { AppLayout } from '../layouts/AppLayout';
import { AnchorButton, Button, ButtonLink } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { CopyButton } from '../components/ui/CopyButton';
import { createInvoice } from '../api/payments';
import { ApiError } from '../api/client';
import { useConsoleConfig } from '../hooks/useConsoleData';
import { createInvoiceSchema, type CreateInvoiceFormValues } from '../schemas/forms';
import { useToastStore } from '../store/toastStore';
import { extractPaymentIdFromUrl, formatAmount, getRuntimeBaseUrl } from '../utils/format';
import { handleTabListKeyDown } from '../utils/tablist';
import styles from './TestingPage.module.css';

interface SessionInvoiceRecord {
  paymentId: string | null;
  pageUrl: string;
  amount: number;
  reference: string;
  createdAt: string;
}

const SESSION_STORAGE_KEY = 'acquiremock_playground_invoices';
const AMOUNT_PRESETS = [1000, 10000, 25000];

function generateOrderRef(): string {
  const stamp = Math.floor(1000 + Math.random() * 9000);
  return `TEST-ORDER-${stamp}`;
}

function loadSessionInvoices(): SessionInvoiceRecord[] {
  try {
    const raw = window.sessionStorage.getItem(SESSION_STORAGE_KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as SessionInvoiceRecord[]) : [];
  } catch {
    return [];
  }
}

export function TestingPage() {
  const baseUrl = getRuntimeBaseUrl();
  const queryClient = useQueryClient();
  const configQuery = useConsoleConfig();
  const pushToast = useToastStore((s) => s.push);

  const [previewMode, setPreviewMode] = useState<'json' | 'curl'>('json');
  const [lastResult, setLastResult] = useState<SessionInvoiceRecord | null>(null);
  const [apiError, setApiError] = useState<string | null>(null);
  const [history, setHistory] = useState<SessionInvoiceRecord[]>(loadSessionInvoices);

  const symbol = configQuery.data?.currency_symbol ?? '$';
  const currencyCode = configQuery.data?.currency_code ?? 'USD';
  const allowLocalWebhooks = configQuery.data?.allow_local_webhooks ?? false;

  const {
    register,
    handleSubmit,
    setValue,
    watch,
    formState: { errors },
  } = useForm<CreateInvoiceFormValues>({
    resolver: zodResolver(createInvoiceSchema),
    defaultValues: {
      amount: 25000,
      reference: 'TEST-ORDER-001',
      webhookUrl: 'https://webhook.site/unique-id',
      redirectUrl: `${baseUrl}/app/payments`,
    },
  });

  const values = watch();

  const requestBodyObj = {
    amount: Number(values.amount) || 0,
    reference: values.reference || '',
    webhookUrl: values.webhookUrl || '',
    redirectUrl: values.redirectUrl || '',
  };

  const jsonPreview = JSON.stringify(requestBodyObj, null, 2);
  const curlPreview = `curl -X POST ${baseUrl}/api/create-invoice \\\n  -H "Content-Type: application/json" \\\n  -d '${JSON.stringify(requestBodyObj)}'`;

  const mutation = useMutation({
    mutationFn: createInvoice,
    onSuccess: (response, payload) => {
      const paymentId = extractPaymentIdFromUrl(response.pageUrl);
      const entry: SessionInvoiceRecord = {
        paymentId,
        pageUrl: response.pageUrl,
        amount: payload.amount,
        reference: payload.reference,
        createdAt: new Date().toLocaleTimeString('en-US', { hour12: false }),
      };
      setLastResult(entry);
      setApiError(null);
      setHistory((prev) => {
        const next = [entry, ...prev].slice(0, 8);
        try {
          window.sessionStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(next));
        } catch {
          // ignore storage quota errors
        }
        return next;
      });
      void queryClient.invalidateQueries({ queryKey: ['console'] });
      pushToast(`Invoice ${payload.reference} created.`, 'success');
    },
    onError: (err) => {
      const message = err instanceof ApiError ? err.message : 'Failed to create invoice';
      setApiError(message);
      pushToast(message, 'error');
    },
  });

  useEffect(() => {
    setApiError(null);
  }, [values.amount, values.reference, values.webhookUrl, values.redirectUrl]);

  function onSubmit(data: CreateInvoiceFormValues) {
    mutation.mutate(data);
  }

  return (
    <AppLayout
      title="Payment testing playground"
      subtitle="Build and submit POST /api/create-invoice requests, inspect the serialized payload, and launch the hosted checkout flow."
      breadcrumbs={[{ label: 'Workspace', to: '/app/overview' }, { label: 'Testing' }]}
    >
      <div className={styles.workbench}>
        <section className={styles.panel} aria-label="Invoice builder">
          <div className={styles.panelHead}>
            <h2 className={styles.panelTitle}>Create invoice</h2>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setValue('reference', generateOrderRef(), { shouldValidate: true })}
            >
              <RefreshCw size={13} strokeWidth={1.75} />
              <span>New reference</span>
            </Button>
          </div>

          <form className={styles.form} onSubmit={handleSubmit(onSubmit)} noValidate>
            <div>
              <Input
                label={`Amount (integer in smallest units, ${configQuery.data?.currency_code ?? 'USD'})`}
                type="number"
                min={1}
                step={1}
                error={errors.amount?.message}
                {...register('amount')}
              />
              <div className={styles.presets}>
                {AMOUNT_PRESETS.map((preset) => (
                  <button
                    key={preset}
                    type="button"
                    className={styles.presetBtn}
                    onClick={() => setValue('amount', preset, { shouldValidate: true })}
                  >
                    {formatAmount(preset, currencyCode, symbol)}
                  </button>
                ))}
              </div>
            </div>

            <Input
              label="Order reference"
              type="text"
              placeholder="ORDER-1042"
              error={errors.reference?.message}
              {...register('reference')}
            />

            <Input
              label="Webhook URL"
              type="url"
              placeholder="https://webhook.site/unique-id"
              error={errors.webhookUrl?.message}
              hint={
                allowLocalWebhooks
                  ? 'ALLOW_LOCAL_WEBHOOKS is enabled on this server.'
                  : 'Private and localhost webhook URLs are blocked unless ALLOW_LOCAL_WEBHOOKS=true.'
              }
              {...register('webhookUrl')}
            />

            <Input
              label="Redirect URL"
              type="url"
              placeholder="http://localhost:8000/app/payments"
              error={errors.redirectUrl?.message}
              {...register('redirectUrl')}
            />

            {apiError ? (
              <div className={styles.errorAlert} role="alert">
                {apiError}
              </div>
            ) : null}

            <Button type="submit" variant="primary" loading={mutation.isPending}>
              Create invoice
            </Button>
          </form>
        </section>

        <div className={styles.rightCol}>
          <section className={styles.panel} aria-label="Request and response inspector">
            <div className={styles.inspectorHead}>
              <div className={styles.tabs} role="tablist" aria-label="Request format">
                <button
                  type="button"
                  role="tab"
                  tabIndex={previewMode === 'json' ? 0 : -1}
                  aria-selected={previewMode === 'json'}
                  className={`${styles.tab} ${previewMode === 'json' ? styles.tabActive : ''}`}
                  onClick={() => setPreviewMode('json')}
                  onKeyDown={(e) =>
                    handleTabListKeyDown(e, ['json', 'curl'] as const, previewMode, setPreviewMode)
                  }
                >
                  Request JSON
                </button>
                <button
                  type="button"
                  role="tab"
                  tabIndex={previewMode === 'curl' ? 0 : -1}
                  aria-selected={previewMode === 'curl'}
                  className={`${styles.tab} ${previewMode === 'curl' ? styles.tabActive : ''}`}
                  onClick={() => setPreviewMode('curl')}
                  onKeyDown={(e) =>
                    handleTabListKeyDown(e, ['json', 'curl'] as const, previewMode, setPreviewMode)
                  }
                >
                  cURL
                </button>
              </div>
              <CopyButton value={previewMode === 'json' ? jsonPreview : curlPreview} compact />
            </div>

            <pre className={styles.codeBox}>
              {previewMode === 'json' ? jsonPreview : curlPreview}
            </pre>

            {lastResult ? (
              <div className={styles.resultBox}>
                <div className={styles.resultTop}>
                  <span className={styles.resultStatus}>200 OK · Invoice created</span>
                  <span className={styles.resultTime}>{lastResult.createdAt}</span>
                </div>

                <div className={styles.urlBox}>
                  <span className="mono-num">{lastResult.pageUrl}</span>
                  <CopyButton value={lastResult.pageUrl} compact />
                </div>

                <div className={styles.resultActions}>
                  <AnchorButton
                    href={lastResult.pageUrl}
                    target="_blank"
                    rel="noreferrer"
                    variant="coral"
                    size="sm"
                  >
                    <span>Open hosted checkout</span>
                    <ExternalLink size={14} strokeWidth={1.75} />
                  </AnchorButton>
                  {lastResult.paymentId ? (
                    <ButtonLink
                      to={`/app/payments/${lastResult.paymentId}`}
                      variant="secondary"
                      size="sm"
                    >
                      Inspect payment record
                    </ButtonLink>
                  ) : null}
                </div>
              </div>
            ) : (
              <p className={styles.placeholderHint}>
                Submit the form on the left to generate a live checkout URL from POST /api/create-invoice.
              </p>
            )}
          </section>

          <section className={styles.panel} aria-label="Sandbox test cards">
            <h2 className={styles.panelTitle}>Sandbox card reference</h2>
            <div className={styles.cardRefRow}>
              <div>
                <div className={styles.cardRefLabel}>Success card (triggers OTP or instant pay if signed in)</div>
                <div className={`${styles.cardRefNum} mono-num`}>4444 4444 4444 4444</div>
              </div>
              <CopyButton value="4444 4444 4444 4444" label="Copy card" compact />
            </div>
            <p className={styles.cardRefNote}>
              Use any future MM/YY expiry and any 3 digits for CVV. Any other card number fails with HTTP 402 INSUFFICIENT_FUNDS.
            </p>
          </section>
        </div>
      </div>

      {history.length > 0 ? (
        <section className={styles.historyPanel} aria-label="Invoices created in this browser session">
          <h2 className={styles.panelTitle}>Session invoice links</h2>
          <div className={styles.historyList}>
            {history.map((item, index) => (
              <div key={`${item.pageUrl}-${index}`} className={styles.historyRow}>
                <div className={styles.historyMeta}>
                  <span className={styles.historyRef}>{item.reference}</span>
                  <span className={`${styles.historyAmount} mono-num`}>
                    {formatAmount(item.amount, currencyCode, symbol)}
                  </span>
                  <span className={styles.historyTime}>{item.createdAt}</span>
                </div>
                <div className={styles.historyActions}>
                  <CopyButton value={item.pageUrl} label="Copy URL" compact />
                  <AnchorButton
                    href={item.pageUrl}
                    target="_blank"
                    rel="noreferrer"
                    variant="secondary"
                    size="sm"
                  >
                    Checkout
                  </AnchorButton>
                  {item.paymentId ? (
                    <ButtonLink
                      to={`/app/payments/${item.paymentId}`}
                      variant="ghost"
                      size="sm"
                    >
                      Inspect
                    </ButtonLink>
                  ) : null}
                </div>
              </div>
            ))}
          </div>
        </section>
      ) : null}
    </AppLayout>
  );
}
