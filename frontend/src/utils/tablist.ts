import type { KeyboardEvent } from 'react';

export function handleTabListKeyDown<T extends string>(
  event: KeyboardEvent<HTMLButtonElement>,
  keys: readonly T[],
  currentKey: T,
  onSelect: (key: T) => void,
): void {
  const index = keys.indexOf(currentKey);
  if (index === -1 || keys.length === 0) return;

  let nextIndex: number | null = null;
  if (event.key === 'ArrowRight' || event.key === 'ArrowDown') {
    nextIndex = (index + 1) % keys.length;
  } else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') {
    nextIndex = (index - 1 + keys.length) % keys.length;
  } else if (event.key === 'Home') {
    nextIndex = 0;
  } else if (event.key === 'End') {
    nextIndex = keys.length - 1;
  }

  if (nextIndex === null) return;
  event.preventDefault();
  onSelect(keys[nextIndex]);

  const tablist = event.currentTarget.closest('[role="tablist"]');
  const tabs = tablist?.querySelectorAll<HTMLButtonElement>('[role="tab"]');
  tabs?.[nextIndex]?.focus();
}
