import type { ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAdminSession } from '../hooks/useAdminAuth';
import { ErrorState, LoadingState } from './ui/StateBlocks';

export function ProtectedConsoleRoute({ children }: { children: ReactNode }) {
  const location = useLocation();
  const sessionQuery = useAdminSession();

  if (sessionQuery.isLoading) {
    return (
      <div style={{ padding: '48px 24px', maxWidth: '480px', margin: '0 auto' }}>
        <LoadingState label="Verifying administrator session" />
      </div>
    );
  }

  if (sessionQuery.isError) {
    return (
      <div style={{ padding: '48px 24px', maxWidth: '480px', margin: '0 auto' }}>
        <ErrorState
          title="Could not verify administrator session"
          message={sessionQuery.error.message}
          onRetry={() => void sessionQuery.refetch()}
        />
      </div>
    );
  }

  if (!sessionQuery.data?.authenticated) {
    return <Navigate to="/app/login" replace state={{ from: location.pathname }} />;
  }

  return <>{children}</>;
}
