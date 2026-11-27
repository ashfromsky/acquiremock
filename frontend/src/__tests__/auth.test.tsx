import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ProtectedConsoleRoute } from '../components/ProtectedConsoleRoute';
import { AdminLoginPage } from '../pages/AdminLoginPage';

function renderWithProviders(initialEntry: string) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <Routes>
          <Route path="/app/login" element={<AdminLoginPage />} />
          <Route
            path="/app/overview"
            element={
              <ProtectedConsoleRoute>
                <div>Console Overview Content</div>
              </ProtectedConsoleRoute>
            }
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('admin authentication and protected routes', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('redirects unauthenticated console visitors to /app/login', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({
          authenticated: false,
          username: null,
          csrf_token: null,
          expires_at: null,
          configured: true,
        }),
        { status: 200, headers: { 'content-type': 'application/json' } },
      ),
    );

    renderWithProviders('/app/overview');

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Administrator sign in' })).toBeInTheDocument();
    });
    expect(screen.queryByText('Console Overview Content')).not.toBeInTheDocument();
  });

  it('renders protected content when admin session is authenticated', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({
          authenticated: true,
          username: 'admin',
          csrf_token: 'csrf-tok',
          expires_at: '2026-11-28T00:00:00',
          configured: true,
        }),
        { status: 200, headers: { 'content-type': 'application/json' } },
      ),
    );

    renderWithProviders('/app/overview');

    await waitFor(() => {
      expect(screen.getByText('Console Overview Content')).toBeInTheDocument();
    });
  });

  it('disables login and shows alert when server admin credentials are unconfigured', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({
          authenticated: false,
          username: null,
          csrf_token: null,
          expires_at: null,
          configured: false,
        }),
        { status: 200, headers: { 'content-type': 'application/json' } },
      ),
    );

    renderWithProviders('/app/login');

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(
        'Administrator authentication is not configured on this server',
      );
    });
    expect(screen.getByRole('button', { name: 'Sign in to console' })).toBeDisabled();
  });

  it('validates empty fields and signs in via /api/admin/login', async () => {
    const user = userEvent.setup();
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = String(input);
      if (url === '/api/admin/session') {
        return new Response(
          JSON.stringify({
            authenticated: false,
            username: null,
            csrf_token: null,
            expires_at: null,
            configured: true,
          }),
          { status: 200, headers: { 'content-type': 'application/json' } },
        );
      }
      if (url === '/api/admin/login') {
        return new Response(
          JSON.stringify({
            authenticated: true,
            username: 'admin',
            csrf_token: 'csrf-new',
            expires_at: '2026-11-28T00:00:00',
            configured: true,
          }),
          { status: 200, headers: { 'content-type': 'application/json' } },
        );
      }
      return new Response('{}', { status: 404 });
    });

    renderWithProviders('/app/login');

    await waitFor(() => {
      expect(screen.getByLabelText('Administrator username')).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: 'Sign in to console' }));
    expect(await screen.findByText('Administrator username is required')).toBeInTheDocument();

    await user.type(screen.getByLabelText('Administrator username'), 'admin');
    await user.type(screen.getByLabelText('Password'), 'SecretPass!123');
    await user.click(screen.getByRole('button', { name: 'Sign in to console' }));

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledWith(
        '/api/admin/login',
        expect.objectContaining({ method: 'POST' }),
      );
      expect(screen.getByText('Console Overview Content')).toBeInTheDocument();
    });
  });
});
