import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchAdminSession, loginAdmin, logoutAdmin } from '../api/admin';

export function useAdminSession() {
  return useQuery({
    queryKey: ['admin', 'session'],
    queryFn: fetchAdminSession,
    staleTime: 15000,
    retry: false,
  });
}

export function useAdminLogin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ username, password }: { username: string; password: string }) =>
      loginAdmin(username, password),
    onSuccess: (session) => {
      queryClient.setQueryData(['admin', 'session'], session);
      void queryClient.invalidateQueries({ queryKey: ['console'] });
    },
  });
}

export function useAdminLogout() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: logoutAdmin,
    onSuccess: () => {
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
    },
  });
}
