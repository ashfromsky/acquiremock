import { X } from 'lucide-react';
import { useToastStore } from '../../store/toastStore';
import styles from './Toast.module.css';

export function ToastViewport() {
  const { items, dismiss } = useToastStore();

  if (items.length === 0) return null;

  return (
    <div className={styles.viewport} aria-live="polite" aria-atomic="true">
      {items.map((item) => (
        <div key={item.id} className={`${styles.toast} ${styles[item.tone]}`} role="status">
          <span className={styles.message}>{item.message}</span>
          <button
            type="button"
            className={styles.close}
            onClick={() => dismiss(item.id)}
            aria-label="Dismiss notification"
          >
            <X size={14} strokeWidth={1.75} />
          </button>
        </div>
      ))}
    </div>
  );
}
