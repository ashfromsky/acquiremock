import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Trash2 } from 'lucide-react';
import { AppLayout } from '../layouts/AppLayout';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { ConfirmDialog } from '../components/ui/ConfirmDialog';
import { EmptyState, ErrorState, LoadingState } from '../components/ui/StateBlocks';
import {
  useAuthSession,
  useDeleteSavedCard,
  useLogout,
  useSendAuthCode,
  useUserInfo,
  useVerifyAuthCode,
} from '../hooks/useAuth';
import { useConsoleConfig } from '../hooks/useConsoleData';
import {
  sendCodeSchema,
  verifyCodeSchema,
  type SendCodeFormValues,
  type VerifyCodeFormValues,
} from '../schemas/forms';
import { useThemeStore } from '../store/themeStore';
import { useToastStore } from '../store/toastStore';
import { formatAmount } from '../utils/format';
import type { SavedCard } from '../types/api';
import styles from './SettingsPage.module.css';

export function SettingsPage() {
  const [pendingEmail, setPendingEmail] = useState<string | null>(null);
  const [authError, setAuthError] = useState<string | null>(null);
  const [cardToDelete, setCardToDelete] = useState<SavedCard | null>(null);

  const { theme, setTheme } = useThemeStore();
  const pushToast = useToastStore((s) => s.push);

  const configQuery = useConsoleConfig();
  const sessionQuery = useAuthSession();
  const isAuthenticated = Boolean(sessionQuery.data?.authenticated);
  const userInfoQuery = useUserInfo(isAuthenticated);

  const sendCodeMutation = useSendAuthCode();
  const verifyCodeMutation = useVerifyAuthCode();
  const logoutMutation = useLogout();
  const deleteCardMutation = useDeleteSavedCard();

  const symbol = configQuery.data?.currency_symbol ?? '$';
  const currencyCode = configQuery.data?.currency_code ?? 'USD';

  const emailForm = useForm<SendCodeFormValues>({
    resolver: zodResolver(sendCodeSchema),
    defaultValues: { email: '' },
  });

  const codeForm = useForm<VerifyCodeFormValues>({
    resolver: zodResolver(verifyCodeSchema),
    defaultValues: { code: '' },
  });

  async function handleSendCode(values: SendCodeFormValues) {
    setAuthError(null);
    try {
      await sendCodeMutation.mutateAsync(values.email);
      setPendingEmail(values.email);
      codeForm.reset({ code: '' });
      pushToast(`Verification code sent to ${values.email}.`, 'info');
    } catch (err) {
      setAuthError(err instanceof Error ? err.message : 'Failed to send verification code');
    }
  }

  async function handleVerifyCode(values: VerifyCodeFormValues) {
    if (!pendingEmail) return;
    setAuthError(null);
    try {
      await verifyCodeMutation.mutateAsync({ email: pendingEmail, code: values.code });
      setPendingEmail(null);
      pushToast(`Signed in as ${pendingEmail}.`, 'success');
    } catch (err) {
      setAuthError(err instanceof Error ? err.message : 'Invalid verification code');
    }
  }

  async function handleLogout() {
    try {
      await logoutMutation.mutateAsync();
      setPendingEmail(null);
      pushToast('Signed out of customer session.', 'info');
    } catch (err) {
      pushToast(err instanceof Error ? err.message : 'Sign out failed', 'error');
    }
  }

  async function handleConfirmDeleteCard() {
    if (!cardToDelete) return;
    try {
      await deleteCardMutation.mutateAsync(cardToDelete.id);
      pushToast(`Removed saved card ${cardToDelete.mask}.`, 'success');
      setCardToDelete(null);
    } catch (err) {
      pushToast(err instanceof Error ? err.message : 'Could not delete card', 'error');
    }
  }

  return (
    <AppLayout
      title="Settings and session"
      subtitle="Authenticate with email OTP to manage saved sandbox cards and inspect gateway configuration."
      breadcrumbs={[{ label: 'Workspace', to: '/app/overview' }, { label: 'Settings' }]}
    >
      <div className={styles.grid}>
        <section className={styles.panel} aria-label="Customer email session and saved cards">
          <h2 className={styles.panelTitle}>Customer session</h2>

          {sessionQuery.isLoading ? (
            <div className={styles.stateBox}>
              <LoadingState label="Checking active session" />
            </div>
          ) : sessionQuery.isError ? (
            <div className={styles.stateBox}>
              <ErrorState
                title="Could not check session"
                message={sessionQuery.error.message}
                onRetry={() => void sessionQuery.refetch()}
              />
            </div>
          ) : isAuthenticated && sessionQuery.data?.email ? (
            <div className={styles.authedBlock}>
              <div className={styles.sessionBar}>
                <div>
                  <div className={styles.sessionLabel}>Active signed HttpOnly session</div>
                  <div className={styles.sessionEmail}>{sessionQuery.data.email}</div>
                </div>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => void handleLogout()}
                  loading={logoutMutation.isPending}
                >
                  Sign out
                </Button>
              </div>

              <div className={styles.subSection}>
                <h3 className={styles.subTitle}>Saved cards</h3>
                {userInfoQuery.isLoading ? (
                  <LoadingState label="Loading saved cards" />
                ) : userInfoQuery.isError ? (
                  <ErrorState
                    title="Could not load saved cards"
                    message={userInfoQuery.error.message}
                    onRetry={() => void userInfoQuery.refetch()}
                  />
                ) : userInfoQuery.data && userInfoQuery.data.cards.length === 0 ? (
                  <EmptyState
                    title="No saved cards for this email"
                    description="Check Save card for future payments during a hosted checkout flow to store a hashed sandbox card here."
                  />
                ) : userInfoQuery.data ? (
                  <div className={styles.cardList}>
                    {userInfoQuery.data.cards.map((card) => (
                      <div key={card.id} className={styles.savedCardRow}>
                        <div>
                          <div className={`${styles.cardMask} mono-num`}>{card.mask}</div>
                          <div className={styles.cardExpiry}>Expires {card.expiry}</div>
                        </div>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setCardToDelete(card)}
                          aria-label={`Remove saved card ${card.mask}`}
                        >
                          <Trash2 size={14} strokeWidth={1.75} />
                          <span>Remove</span>
                        </Button>
                      </div>
                    ))}
                  </div>
                ) : null}
              </div>

              <div className={styles.subSection}>
                <h3 className={styles.subTitle}>Recent settled operations</h3>
                {userInfoQuery.data && userInfoQuery.data.operations.length === 0 ? (
                  <p className={styles.mutedNote}>No completed operations recorded for this email yet.</p>
                ) : userInfoQuery.data ? (
                  <div className={styles.opsList}>
                    {userInfoQuery.data.operations.map((op, idx) => (
                      <div key={`${op.reference}-${idx}`} className={styles.opRow}>
                        <div>
                          <div className={styles.opRef}>{op.reference}</div>
                          <div className={styles.opMeta}>
                            {op.date} · {op.card_mask}
                          </div>
                        </div>
                        <span className={`${styles.opAmount} mono-num`}>
                          {op.formatted_amount || formatAmount(op.amount, currencyCode, symbol)}
                        </span>
                      </div>
                    ))}
                  </div>
                ) : null}
              </div>
            </div>
          ) : (
            <div className={styles.loginBlock}>
              <p className={styles.panelDesc}>
                Sign in using the same email OTP flow as hosted checkout. When SMTP is unconfigured, the 4-digit code is logged to the FastAPI console output.
              </p>

              {!pendingEmail ? (
                <form
                  className={styles.form}
                  onSubmit={emailForm.handleSubmit(handleSendCode)}
                  noValidate
                >
                  <Input
                    label="Email address"
                    type="email"
                    placeholder="you@example.com"
                    error={emailForm.formState.errors.email?.message}
                    {...emailForm.register('email')}
                  />
                  {authError ? (
                    <div className={styles.errorAlert} role="alert">
                      {authError}
                    </div>
                  ) : null}
                  <Button type="submit" variant="primary" loading={sendCodeMutation.isPending}>
                    Send verification code
                  </Button>
                </form>
              ) : (
                <form
                  className={styles.form}
                  onSubmit={codeForm.handleSubmit(handleVerifyCode)}
                  noValidate
                >
                  <p className={styles.codeSentInfo}>
                    Enter the 4-digit code sent to <strong>{pendingEmail}</strong>.
                  </p>
                  <Input
                    label="4-digit code"
                    type="text"
                    inputMode="numeric"
                    maxLength={4}
                    placeholder="0000"
                    error={codeForm.formState.errors.code?.message}
                    {...codeForm.register('code')}
                  />
                  {authError ? (
                    <div className={styles.errorAlert} role="alert">
                      {authError}
                    </div>
                  ) : null}
                  <div className={styles.formActions}>
                    <Button type="submit" variant="primary" loading={verifyCodeMutation.isPending}>
                      Verify and sign in
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      onClick={() => {
                        setPendingEmail(null);
                        setAuthError(null);
                      }}
                    >
                      Change email
                    </Button>
                  </div>
                </form>
              )}
            </div>
          )}
        </section>

        <div className={styles.rightColumn}>
          <section className={styles.panel} aria-label="Appearance settings">
            <h2 className={styles.panelTitle}>Appearance</h2>
            <p className={styles.panelDesc}>
              Applies across the developer workspace, public pages, and hosted checkout templates.
            </p>
            <div className={styles.themeChoices} role="radiogroup" aria-label="Interface theme">
              <button
                type="button"
                role="radio"
                aria-checked={theme === 'light'}
                className={`${styles.themeBtn} ${theme === 'light' ? styles.themeBtnActive : ''}`}
                onClick={() => setTheme('light')}
              >
                Warm Light
              </button>
              <button
                type="button"
                role="radio"
                aria-checked={theme === 'dark'}
                className={`${styles.themeBtn} ${theme === 'dark' ? styles.themeBtnActive : ''}`}
                onClick={() => setTheme('dark')}
              >
                Charcoal Dark
              </button>
            </div>
          </section>

          <section className={styles.panel} aria-label="Gateway environment configuration">
            <h2 className={styles.panelTitle}>Gateway configuration</h2>
            <p className={styles.panelDesc}>
              Read-only runtime parameters loaded from server environment variables.
            </p>

            {configQuery.isLoading ? (
              <div className={styles.stateBox}>
                <LoadingState label="Loading gateway config" />
              </div>
            ) : configQuery.isError ? (
              <div className={styles.stateBox}>
                <ErrorState
                  title="Could not load config"
                  message={configQuery.error.message}
                  onRetry={() => void configQuery.refetch()}
                />
              </div>
            ) : configQuery.data ? (
              <dl className={styles.configList}>
                <div className={styles.configRow}>
                  <dt>Gateway version</dt>
                  <dd className="mono-num">v{configQuery.data.version}</dd>
                </div>
                <div className={styles.configRow}>
                  <dt>BASE_URL</dt>
                  <dd className="mono-num">{configQuery.data.base_url}</dd>
                </div>
                <div className={styles.configRow}>
                  <dt>Currency</dt>
                  <dd className="mono-num">
                    {configQuery.data.currency_code} ({configQuery.data.currency_symbol})
                  </dd>
                </div>
                <div className={styles.configRow}>
                  <dt>SMTP delivery</dt>
                  <dd>{configQuery.data.smtp_enabled ? 'Enabled' : 'Console fallback'}</dd>
                </div>
                <div className={styles.configRow}>
                  <dt>ALLOW_LOCAL_WEBHOOKS</dt>
                  <dd className="mono-num">{String(configQuery.data.allow_local_webhooks)}</dd>
                </div>
                <div className={styles.configRow}>
                  <dt>Payment TTL</dt>
                  <dd className="mono-num">{configQuery.data.payment_ttl_minutes} minutes</dd>
                </div>
                <div className={styles.configRow}>
                  <dt>Max webhook attempts</dt>
                  <dd className="mono-num">{configQuery.data.max_webhook_attempts}</dd>
                </div>
              </dl>
            ) : null}
          </section>
        </div>
      </div>

      <ConfirmDialog
        open={Boolean(cardToDelete)}
        title="Remove saved card"
        description={
          cardToDelete
            ? `Remove ${cardToDelete.mask} (expires ${cardToDelete.expiry}) from your saved sandbox cards?`
            : ''
        }
        confirmLabel="Remove card"
        loading={deleteCardMutation.isPending}
        onCancel={() => setCardToDelete(null)}
        onConfirm={() => void handleConfirmDeleteCard()}
      />
    </AppLayout>
  );
}
