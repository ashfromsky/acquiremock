import { useEffect } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ToastViewport } from './components/ui/Toast';
import { HomePage } from './pages/HomePage';
import { OverviewPage } from './pages/OverviewPage';
import { PaymentsPage } from './pages/PaymentsPage';
import { PaymentDetailPage } from './pages/PaymentDetailPage';
import { TestingPage } from './pages/TestingPage';
import { WebhooksPage } from './pages/WebhooksPage';
import { SettingsPage } from './pages/SettingsPage';
import { NotFoundPage } from './pages/NotFoundPage';
import { applyThemeToDom, useThemeStore } from './store/themeStore';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 10000,
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

export function App() {
  const theme = useThemeStore((s) => s.theme);

  useEffect(() => {
    applyThemeToDom(theme);
  }, [theme]);

  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/test" element={<TestingPage />} />

          <Route path="/app" element={<Navigate to="/app/overview" replace />} />
          <Route path="/app/overview" element={<OverviewPage />} />
          <Route path="/app/payments" element={<PaymentsPage />} />
          <Route path="/app/payments/:paymentId" element={<PaymentDetailPage />} />
          <Route path="/app/testing" element={<TestingPage />} />
          <Route path="/app/webhooks" element={<WebhooksPage />} />
          <Route path="/app/settings" element={<SettingsPage />} />
          <Route path="/app/login" element={<Navigate to="/app/settings" replace />} />

          <Route path="/merchant/login" element={<Navigate to="/app/settings" replace />} />
          <Route path="/merchant/dashboard" element={<Navigate to="/app/overview" replace />} />

          <Route path="*" element={<NotFoundPage />} />
        </Routes>
        <ToastViewport />
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
