import { useEffect } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ErrorBoundary } from './components/ErrorBoundary';
import { ProtectedConsoleRoute } from './components/ProtectedConsoleRoute';
import { ToastViewport } from './components/ui/Toast';
import { ADMIN_UNAUTHORIZED_EVENT, ApiError } from './api/client';
import { AdminLoginPage } from './pages/AdminLoginPage';
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
      retry: (failureCount, error) => {
        if (error instanceof ApiError && [401, 403, 404, 503].includes(error.status)) {
          return false;
        }
        return failureCount < 1;
      },
    },
  },
});

export function App() {
  const theme = useThemeStore((s) => s.theme);

  useEffect(() => {
    applyThemeToDom(theme);
  }, [theme]);

  useEffect(() => {
    function handleUnauthorized() {
      queryClient.setQueryData(['admin', 'session'], (prev: unknown) => {
        const configured =
          prev && typeof prev === 'object' && 'configured' in prev
            ? Boolean((prev as { configured?: boolean }).configured)
            : true;
        return {
          authenticated: false,
          username: null,
          csrf_token: null,
          expires_at: null,
          configured,
        };
      });
      queryClient.removeQueries({ queryKey: ['console'] });
    }

    window.addEventListener(ADMIN_UNAUTHORIZED_EVENT, handleUnauthorized);
    return () => window.removeEventListener(ADMIN_UNAUTHORIZED_EVENT, handleUnauthorized);
  }, []);

  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route
              path="/test"
              element={
                <ProtectedConsoleRoute>
                  <TestingPage />
                </ProtectedConsoleRoute>
              }
            />

            <Route path="/app/login" element={<AdminLoginPage />} />
            <Route path="/app" element={<Navigate to="/app/overview" replace />} />
            <Route
              path="/app/overview"
              element={
                <ProtectedConsoleRoute>
                  <OverviewPage />
                </ProtectedConsoleRoute>
              }
            />
            <Route
              path="/app/payments"
              element={
                <ProtectedConsoleRoute>
                  <PaymentsPage />
                </ProtectedConsoleRoute>
              }
            />
            <Route
              path="/app/payments/:paymentId"
              element={
                <ProtectedConsoleRoute>
                  <PaymentDetailPage />
                </ProtectedConsoleRoute>
              }
            />
            <Route
              path="/app/testing"
              element={
                <ProtectedConsoleRoute>
                  <TestingPage />
                </ProtectedConsoleRoute>
              }
            />
            <Route
              path="/app/webhooks"
              element={
                <ProtectedConsoleRoute>
                  <WebhooksPage />
                </ProtectedConsoleRoute>
              }
            />
            <Route
              path="/app/settings"
              element={
                <ProtectedConsoleRoute>
                  <SettingsPage />
                </ProtectedConsoleRoute>
              }
            />

            <Route path="/merchant/login" element={<Navigate to="/app/login" replace />} />
            <Route path="/merchant/dashboard" element={<Navigate to="/app/overview" replace />} />

            <Route path="*" element={<NotFoundPage />} />
          </Routes>
          <ToastViewport />
        </BrowserRouter>
      </QueryClientProvider>
    </ErrorBoundary>
  );
}

export default App;
