import { create } from 'zustand';

export type Theme = 'light' | 'dark';

function resolveInitialTheme(): Theme {
  if (typeof window === 'undefined') return 'light';
  const saved = window.localStorage.getItem('theme');
  if (saved === 'dark' || saved === 'light') return saved;
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

export function applyThemeToDom(theme: Theme): void {
  if (typeof document === 'undefined') return;
  if (theme === 'dark') {
    document.documentElement.dataset.theme = 'dark';
    document.body.classList.add('dark-mode');
  } else {
    delete document.documentElement.dataset.theme;
    document.body.classList.remove('dark-mode');
  }
}

interface ThemeState {
  theme: Theme;
  setTheme: (theme: Theme) => void;
  toggleTheme: () => void;
}

export const useThemeStore = create<ThemeState>((set, get) => ({
  theme: resolveInitialTheme(),
  setTheme: (theme) => {
    window.localStorage.setItem('theme', theme);
    applyThemeToDom(theme);
    set({ theme });
  },
  toggleTheme: () => {
    const next: Theme = get().theme === 'dark' ? 'light' : 'dark';
    get().setTheme(next);
  },
}));
