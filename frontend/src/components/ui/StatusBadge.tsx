import styles from './StatusBadge.module.css';

const LABEL_MAP: Record<string, string> = {
  paid: 'Paid',
  success: 'Succeeded',
  pending: 'Pending',
  waiting_for_otp: 'Awaiting OTP',
  failed: 'Failed',
  expired: 'Expired',
  refunded: 'Refunded',
};

const TONE_MAP: Record<string, string> = {
  paid: 'paid',
  success: 'paid',
  pending: 'pending',
  waiting_for_otp: 'otp',
  failed: 'failed',
  expired: 'expired',
  refunded: 'pending',
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
