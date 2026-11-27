import { create } from 'zustand';

export type ToastTone = 'info' | 'success' | 'error';

export interface ToastItem {
  id: string;
  message: string;
  tone: ToastTone;
}

interface ToastState {
  items: ToastItem[];
  push: (message: string, tone?: ToastTone) => void;
  dismiss: (id: string) => void;
}

export const useToastStore = create<ToastState>((set) => ({
  items: [],
  push: (message, tone = 'info') => {
    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    set((state) => ({ items: [...state.items.slice(-3), { id, message, tone }] }));
    window.setTimeout(() => {
      set((state) => ({ items: state.items.filter((t) => t.id !== id) }));
    }, 4200);
  },
  dismiss: (id) => set((state) => ({ items: state.items.filter((t) => t.id !== id) })),
}));
