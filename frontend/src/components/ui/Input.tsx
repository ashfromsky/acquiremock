import { forwardRef, useId } from 'react';
import type { InputHTMLAttributes, TextareaHTMLAttributes } from 'react';
import styles from './Input.module.css';

interface FieldBaseProps {
  label: string;
  error?: string;
  hint?: string;
}

type InputProps = FieldBaseProps & InputHTMLAttributes<HTMLInputElement>;

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { label, error, hint, id, className, ...rest },
  ref,
) {
  const autoId = useId();
  const fieldId = id ?? autoId;
  const errorId = `${fieldId}-error`;
  const hintId = `${fieldId}-hint`;

  return (
    <div className={styles.field}>
      <label className={styles.label} htmlFor={fieldId}>
        {label}
      </label>
      <input
        ref={ref}
        id={fieldId}
        className={[styles.input, error ? styles.invalid : '', className].filter(Boolean).join(' ')}
        aria-invalid={Boolean(error) || undefined}
        aria-describedby={error ? errorId : hint ? hintId : undefined}
        {...rest}
      />
      {error ? (
        <p id={errorId} className={styles.error} role="alert">
          {error}
        </p>
      ) : hint ? (
        <p id={hintId} className={styles.hint}>
          {hint}
        </p>
      ) : null}
    </div>
  );
});

type TextareaProps = FieldBaseProps & TextareaHTMLAttributes<HTMLTextAreaElement>;

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(function Textarea(
  { label, error, hint, id, className, ...rest },
  ref,
) {
  const autoId = useId();
  const fieldId = id ?? autoId;
  const errorId = `${fieldId}-error`;
  const hintId = `${fieldId}-hint`;

  return (
    <div className={styles.field}>
      <label className={styles.label} htmlFor={fieldId}>
        {label}
      </label>
      <textarea
        ref={ref}
        id={fieldId}
        className={[styles.textarea, error ? styles.invalid : '', className].filter(Boolean).join(' ')}
        aria-invalid={Boolean(error) || undefined}
        aria-describedby={error ? errorId : hint ? hintId : undefined}
        {...rest}
      />
      {error ? (
        <p id={errorId} className={styles.error} role="alert">
          {error}
        </p>
      ) : hint ? (
        <p id={hintId} className={styles.hint}>
          {hint}
        </p>
      ) : null}
    </div>
  );
});
