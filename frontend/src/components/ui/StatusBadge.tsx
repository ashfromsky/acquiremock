import styles from './StatusBadge.module.css';

const LABEL_MAP: Record<string, string> = {
  paid: 'Paid',
  success: 'Succeeded',
  succeeded: 'Succeeded',
  pending: 'Pending',
  waiting_for_otp: 'Awaiting OTP',
  scheduled_retry: 'Retry scheduled',
  exhausted: 'Attempts exhausted',
  never_attempted: 'Not dispatched',
  failed: 'Failed',
  expired: 'Expired',
  refunded: 'Refunded',
  manual: 'Manual',
  auto: 'Auto',
};

const TONE_MAP: Record<string, string> = {
  paid: 'paid',
  success: 'paid',
  succeeded: 'paid',
  pending: 'pending',
  waiting_for_otp: 'otp',
  scheduled_retry: 'pending',
  exhausted: 'failed',
  never_attempted: 'expired',
  failed: 'failed',
  expired: 'expired',
  refunded: 'pending',
  manual: 'otp',
  auto: 'expired',
};

interface StatusBadgeProps {
  status: string | null | undefined;
}

export function StatusBadge({ status }: StatusBadgeProps) {
  const key = (status || 'pending').toLowerCase();
  const label = LABEL_MAP[key] || status || 'Unknown';
  const tone = TONE_MAP[key] || 'pending';

  return <span className={`${styles.badge} ${styles[tone]}`}>{label}</span>;
}
