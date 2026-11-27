import { useState } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { PublicLayout } from '../layouts/PublicLayout';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { LoadingState } from '../components/ui/StateBlocks';
import { ApiError } from '../api/client';
import { useAdminLogin, useAdminSession } from '../hooks/useAdminAuth';
import { adminLoginSchema, type AdminLoginFormValues } from '../schemas/forms';
import styles from './AdminLoginPage.module.css';

export function AdminLoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const sessionQuery = useAdminSession();
  const loginMutation = useAdminLogin();
  const [loginError, setLoginError] = useState<string | null>(null);

  const fromPath =
    (location.state as { from?: string } | null)?.from || '/app/overview';

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<AdminLoginFormValues>({
    resolver: zodResolver(adminLoginSchema),
    defaultValues: { username: '', password: '' },
  });

  if (sessionQuery.isLoading) {
    return (
      <PublicLayout>
        <section className={styles.wrap}>
          <LoadingState label="Checking administrator session" />
        </section>
      </PublicLayout>
    );
  }

  if (sessionQuery.data?.authenticated) {
    return <Navigate to={fromPath} replace />;
  }

  const isConfigured = sessionQuery.data?.configured ?? true;

  async function onSubmit(values: AdminLoginFormValues) {
    setLoginError(null);
    try {
      await loginMutation.mutateAsync(values);
      navigate(fromPath, { replace: true });
    } catch (err) {
      if (err instanceof ApiError) {
        setLoginError(err.message);
      } else {
        setLoginError('Unable to sign in to administrator console.');
      }
    }
  }

  return (
    <PublicLayout>
      <section className={styles.wrap} aria-label="Administrator sign in">
        <div className={styles.card}>
          <span className={styles.eyebrow}>Developer console</span>
          <h1 className={styles.title}>Administrator sign in</h1>
          <p className={styles.subtitle}>
            Sign in with the server-configured administrator account to inspect payments, webhook logs, and gateway settings.
          </p>

          {!isConfigured ? (
            <div className={styles.configAlert} role="alert">
              Administrator authentication is not configured on this server. Set{' '}
              <code>ADMIN_USERNAME</code> and <code>ADMIN_PASSWORD_HASH</code> in the backend environment and restart the service.
            </div>
          ) : null}

          <form className={styles.form} onSubmit={handleSubmit(onSubmit)} noValidate>
            <Input
              label="Administrator username"
              type="text"
              autoComplete="username"
              placeholder="admin"
              disabled={!isConfigured}
              error={errors.username?.message}
              {...register('username')}
            />

            <Input
              label="Password"
              type="password"
              autoComplete="current-password"
              placeholder="Enter administrator password"
              disabled={!isConfigured}
              error={errors.password?.message}
              {...register('password')}
            />

            {loginError ? (
              <div className={styles.errorAlert} role="alert">
                {loginError}
              </div>
            ) : null}

            <Button
              type="submit"
              variant="primary"
              disabled={!isConfigured}
              loading={loginMutation.isPending}
            >
              Sign in to console
            </Button>
          </form>
        </div>
      </section>
    </PublicLayout>
  );
}
