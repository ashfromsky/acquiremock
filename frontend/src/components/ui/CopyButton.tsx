import { useState } from 'react';
import { Check, Copy } from 'lucide-react';
import styles from './CopyButton.module.css';

interface CopyButtonProps {
  value: string;
  label?: string;
  compact?: boolean;
}

export function CopyButton({ value, label = 'Copy', compact = false }: CopyButtonProps) {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      setCopied(false);
    }
  }

  return (
    <button
      type="button"
      className={`${styles.btn} ${compact ? styles.compact : ''}`}
      onClick={handleCopy}
      aria-label={copied ? 'Copied to clipboard' : label}
    >
      {copied ? <Check size={14} strokeWidth={1.75} /> : <Copy size={14} strokeWidth={1.75} />}
      <span>{copied ? 'Copied' : label}</span>
    </button>
  );
}
