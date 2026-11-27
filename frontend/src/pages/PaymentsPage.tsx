import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { RefreshCw, Search } from 'lucide-react';
import { AppLayout } from '../layouts/AppLayout';
import { Button } from '../components/ui/Button';
import { StatusBadge } from '../components/ui/StatusBadge';
import { EmptyState, ErrorState, LoadingState } from '../components/ui/StateBlocks';
import { useConsoleConfig, useConsolePayments } from '../hooks/useConsoleData';
import { formatAmount, formatDateTime, formatShortId } from '../utils/format';
import styles from './PaymentsPage.module.css';

const STATUS_TABS = [
  { key: 'all', label: 'All' },
  { key: 'paid', label: 'Paid' },
  { key: 'pending', label: 'Pending' },
  { key: 'waiting_for_otp', label: 'Awaiting OTP' },
  { key: 'failed', label: 'Failed' },
  { key: 'expired', label: 'Expired' },
];

export function PaymentsPage() {
  const [status, setStatus] = useState('all');
  const [searchInput, setSearchInput] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedSearch(searchInput), 250);
    return () => window.clearTimeout(timer);
  }, [searchInput]);

  const configQuery = useConsoleConfig();
  const paymentsQuery = useConsolePayments({
    status,
    q: debouncedSearch,
    limit: 50,
    offset: 0,
  });

  const symbol = configQuery.data?.currency_symbol ?? '$';
  const hasFilters = status !== 'all' || Boolean(debouncedSearch.trim());

  return (
    <AppLayout
      title="Payments"
      subtitle="Inspect invoices created via API or Playground, filter by lifecycle status, and review webhook attempts."
      breadcrumbs={[{ label: 'Workspace', to: '/app/overview' }, { label: 'Payments' }]}
      actions={
        <Link to="/app/testing">
          <Button variant="primary" size="sm">
            Create test payment
          </Button>
        </Link>
      }
    >
      <div className={styles.toolbar}>
        <div className={styles.tabs} role="tablist" aria-label="Filter payments by status">
          {STATUS_TABS.map((tab) => (
            <button
              key={tab.key}
              type="button"
              role="tab"
              aria-selected={status === tab.key}
              className={`${styles.tab} ${status === tab.key ? styles.tabActive : ''}`}
              onClick={() => setStatus(tab.key)}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div className={styles.searchGroup}>
          <div className={styles.searchField}>
            <Search size={15} strokeWidth={1.75} className={styles.searchIcon} aria-hidden="true" />
            <input
              type="search"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="Search reference or payment ID"
              aria-label="Search payments by reference or ID"
              className={styles.searchInput}
            />
          </div>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => void paymentsQuery.refetch()}
            loading={paymentsQuery.isFetching && !paymentsQuery.isLoading}
          >
            <RefreshCw size={14} strokeWidth={1.75} />
            <span>Refresh</span>
          </Button>
        </div>
      </div>

      {paymentsQuery.isLoading ? (
        <LoadingState label="Loading payments" />
      ) : paymentsQuery.isError ? (
        <ErrorState
          title="Could not load payments"
          message={paymentsQuery.error.message}
          onRetry={() => void paymentsQuery.refetch()}
        />
      ) : paymentsQuery.data && paymentsQuery.data.items.length === 0 ? (
        hasFilters ? (
          <EmptyState
            title="No payments match your filters"
            description="Adjust the status filter or clear your search query to see other payment records."
            action={
              <Button
                variant="secondary"
                size="sm"
                onClick={() => {
                  setStatus('all');
                  setSearchInput('');
                }}
              >
                Reset filters
              </Button>
            }
          />
        ) : (
          <EmptyState
            title="No payments have been created yet"
            description="Create a test invoice in the Playground or send a POST /api/create-invoice request from your application."
            action={
              <Link to="/app/testing">
                <Button variant="primary" size="sm">
                  Open payment playground
                </Button>
              </Link>
            }
          />
        )
      ) : paymentsQuery.data ? (
        <div className={styles.tableContainer}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Reference and ID</th>
                <th className={styles.numCol}>Amount</th>
                <th>Status</th>
                <th>Card</th>
                <th>Webhook</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {paymentsQuery.data.items.map((payment) => (
                <tr key={payment.id}>
                  <td data-label="Reference">
                    <Link to={`/app/payments/${payment.id}`} className={styles.refLink}>
                      <span className={styles.refName}>{payment.reference}</span>
                      <span className={styles.paymentId}>{formatShortId(payment.id)}</span>
                    </Link>
                  </td>
                  <td data-label="Amount" className={`${styles.numCol} mono-num`}>
                    {formatAmount(payment.amount, symbol)}
                  </td>
                  <td data-label="Status">
                    <StatusBadge status={payment.status} />
                  </td>
                  <td data-label="Card" className="mono-num">
                    {payment.card_mask || 'Not entered'}
                  </td>
                  <td data-label="Webhook">
                    {payment.webhook_status ? (
                      <div className={styles.webhookCell}>
                        <StatusBadge status={payment.webhook_status} />
                        <span className={styles.attemptsText}>
                          {payment.webhook_attempts} {payment.webhook_attempts === 1 ? 'attempt' : 'attempts'}
                        </span>
                      </div>
                    ) : (
                      <span className={styles.mutedText}>Not dispatched</span>
                    )}
                  </td>
                  <td data-label="Created" className={styles.mutedText}>
                    {formatDateTime(payment.created_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          <div className={styles.tableFooter}>
            <span>
              Showing {paymentsQuery.data.items.length} of {paymentsQuery.data.total} payments
            </span>
          </div>
        </div>
      ) : null}
    </AppLayout>
  );
}
