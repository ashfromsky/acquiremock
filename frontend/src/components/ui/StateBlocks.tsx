import type { ReactNode } from 'react';
import { Button } from './Button';
import styles from './StateBlocks.module.css';

export function LoadingState({ label }: { label: string }) {
  return (
    <div className={styles.block} role="status" aria-live="polite">
      <div className={styles.spinner} aria-hidden="true" />
      <p className={styles.title}>{label}</p>
    </div>
  );
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className={styles.block}>
      <p className={styles.title}>{title}</p>
      <p className={styles.description}>{description}</p>
      {action ? <div className={styles.action}>{action}</div> : null}
    </div>
  );
}

export function ErrorState({
  title,
  message,
  onRetry,
}: {
  title: string;
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div className={`${styles.block} ${styles.errorBlock}`} role="alert">
      <p className={styles.title}>{title}</p>
      <p className={styles.description}>{message}</p>
      {onRetry ? (
        <div className={styles.action}>
          <Button variant="secondary" size="sm" onClick={onRetry}>
            Retry
          </Button>
        </div>
      ) : null}
    </div>
  );
}
