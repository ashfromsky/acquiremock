import { Link } from 'react-router-dom';
import { AppLayout } from '../layouts/AppLayout';
import { Button } from '../components/ui/Button';
import { StatusBadge } from '../components/ui/StatusBadge';
import { EmptyState, ErrorState, LoadingState } from '../components/ui/StateBlocks';
import { useConsoleConfig, useConsoleOverview, useHealth } from '../hooks/useConsoleData';
import { formatAmount, formatDateTime, formatShortId } from '../utils/format';
import styles from './OverviewPage.module.css';

export function OverviewPage() {
  const healthQuery = useHealth();
  const configQuery = useConsoleConfig();
  const overviewQuery = useConsoleOverview();

  const symbol = configQuery.data?.currency_symbol ?? '$';
  const currencyCode = configQuery.data?.currency_code ?? healthQuery.data?.currency ?? 'USD';

  return (
    <AppLayout
      title="Gateway overview"
      subtitle="Live payment totals, webhook delivery metrics, and runtime configuration from this AcquireMock instance."
      breadcrumbs={[{ label: 'Workspace' }, { label: 'Overview' }]}
      actions={
        <Link to="/app/testing">
          <Button variant="primary" size="sm">
            Create test payment
          </Button>
        </Link>
      }
    >
      <section className={styles.statusStrip} aria-label="Gateway runtime status">
        <div className={styles.statusCell}>
          <span className={styles.cellLabel}>Service</span>
          <span className={styles.cellValue}>
            <span
              className={`${styles.dot} ${healthQuery.data?.status === 'ok' ? styles.dotOk : styles.dotOff}`}
              aria-hidden="true"
            />
            {healthQuery.isLoading
              ? 'Checking'
              : healthQuery.isError
                ? 'Unavailable'
                : `Online (v${healthQuery.data?.version})`}
          </span>
        </div>
        <div className={styles.statusCell}>
          <span className={styles.cellLabel}>Currency</span>
          <span className={`${styles.cellValue} mono-num`}>
            {currencyCode} ({symbol})
          </span>
        </div>
        <div className={styles.statusCell}>
          <span className={styles.cellLabel}>Email OTP delivery</span>
          <span className={styles.cellValue}>
            {configQuery.data
              ? configQuery.data.smtp_enabled
                ? 'SMTP configured'
                : 'Console logging'
              : 'Loading'}
          </span>
        </div>
        <div className={styles.statusCell}>
          <span className={styles.cellLabel}>Local webhooks</span>
          <span className={styles.cellValue}>
            {configQuery.data
              ? configQuery.data.allow_local_webhooks
                ? 'Allowed'
                : 'Blocked'
              : 'Loading'}
          </span>
        </div>
      </section>

      {overviewQuery.isLoading ? (
        <div className={styles.stateSpacing}>
          <LoadingState label="Loading payment and webhook metrics" />
        </div>
      ) : overviewQuery.isError ? (
        <div className={styles.stateSpacing}>
          <ErrorState
            title="Could not load overview metrics"
            message={overviewQuery.error.message}
            onRetry={() => void overviewQuery.refetch()}
          />
        </div>
      ) : overviewQuery.data ? (
        <>
          <section className={styles.metricsGrid} aria-label="Summary metrics">
            <div className={styles.metricBlock}>
              <span className={styles.metricLabel}>Total payments</span>
              <span className={`${styles.metricValue} mono-num`}>
                {overviewQuery.data.payments.total}
              </span>
              <span className={styles.metricSub}>
                {overviewQuery.data.payments.failed} failed · {overviewQuery.data.payments.expired} expired
              </span>
            </div>

            <div className={styles.metricBlock}>
              <span className={styles.metricLabel}>Paid volume</span>
              <span className={`${styles.metricValue} mono-num`}>
                {formatAmount(overviewQuery.data.payments.paid_volume, symbol)}
              </span>
              <span className={styles.metricSub}>
                Across {overviewQuery.data.payments.paid} settled payments
              </span>
            </div>

            <div className={styles.metricBlock}>
              <span className={styles.metricLabel}>In progress</span>
              <span className={`${styles.metricValue} mono-num`}>
                {overviewQuery.data.payments.pending + overviewQuery.data.payments.waiting_for_otp}
              </span>
              <span className={styles.metricSub}>
                {overviewQuery.data.payments.pending} pending · {overviewQuery.data.payments.waiting_for_otp} awaiting OTP
              </span>
            </div>

            <div className={styles.metricBlock}>
              <span className={styles.metricLabel}>Webhook delivery rate</span>
              <span className={`${styles.metricValue} mono-num`}>
                {overviewQuery.data.webhooks.success_rate === null
                  ? 'No deliveries'
                  : `${overviewQuery.data.webhooks.success_rate}%`}
              </span>
              <span className={styles.metricSub}>
                {overviewQuery.data.webhooks.succeeded} succeeded · {overviewQuery.data.webhooks.failed} failed
              </span>
            </div>
          </section>

          <div className={styles.mainSplit}>
            <section className={styles.recentSection} aria-label="Recent payments">
              <div className={styles.sectionHead}>
                <h2 className={styles.sectionTitle}>Recent payments</h2>
                <Link to="/app/payments" className={styles.sectionLink}>
                  View all
                </Link>
              </div>

              {overviewQuery.data.recent_payments.length === 0 ? (
                <EmptyState
                  title="No payments recorded yet"
                  description="Create your first test invoice in the Playground to walk through checkout, OTP verification, and webhook delivery."
                  action={
                    <Link to="/app/testing">
                      <Button variant="primary" size="sm">
                        Create test invoice
                      </Button>
                    </Link>
                  }
                />
              ) : (
                <div className={styles.tableWrap}>
                  <table className={styles.table}>
                    <thead>
                      <tr>
                        <th>Reference</th>
                        <th>Status</th>
                        <th className={styles.numCol}>Amount</th>
                        <th>Created</th>
                      </tr>
                    </thead>
                    <tbody>
                      {overviewQuery.data.recent_payments.map((payment) => (
                        <tr key={payment.id}>
                          <td>
                            <Link to={`/app/payments/${payment.id}`} className={styles.rowLink}>
                              <span className={styles.refText}>{payment.reference}</span>
                              <span className={styles.idText}>{formatShortId(payment.id)}</span>
                            </Link>
                          </td>
                          <td>
                            <StatusBadge status={payment.status} />
                          </td>
                          <td className={`${styles.numCol} mono-num`}>
                            {formatAmount(payment.amount, symbol)}
                          </td>
                          <td className={styles.dateCol}>{formatDateTime(payment.created_at)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>

            <aside className={styles.actionsSection} aria-label="Quick entry points">
              <h2 className={styles.sectionTitle}>Quick entry points</h2>
              <div className={styles.actionList}>
                <Link to="/app/testing" className={styles.actionRow}>
                  <span className={styles.actionTitle}>Payment playground</span>
                  <span className={styles.actionDesc}>
                    Generate an invoice, inspect the POST payload, and open hosted checkout.
                  </span>
                </Link>
                <Link to="/app/webhooks" className={styles.actionRow}>
                  <span className={styles.actionTitle}>Webhook verifier and logs</span>
                  <span className={styles.actionDesc}>
                    Inspect delivery attempts, retry failures, and verify HMAC-SHA256 signatures.
                  </span>
                </Link>
                <Link to="/app/settings" className={styles.actionRow}>
                  <span className={styles.actionTitle}>Session and saved cards</span>
                  <span className={styles.actionDesc}>
                    Sign in with email OTP to view saved cards and inspect gateway configuration.
                  </span>
                </Link>
                <a href="/docs" target="_blank" rel="noreferrer" className={styles.actionRow}>
                  <span className={styles.actionTitle}>OpenAPI Swagger UI</span>
                  <span className={styles.actionDesc}>
                    Explore raw FastAPI endpoint schemas and response models.
                  </span>
                </a>
              </div>
            </aside>
          </div>
        </>
      ) : null}
    </AppLayout>
  );
}
