import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  deleteSavedCard,
  fetchAuthSession,
  fetchUserInfo,
  logoutAuth,
  sendAuthCode,
  verifyAuthCode,
} from '../api/auth';

export function useAuthSession() {
  return useQuery({
    queryKey: ['auth', 'session'],
    queryFn: fetchAuthSession,
  });
}

export function useUserInfo(enabled: boolean) {
  return useQuery({
    queryKey: ['auth', 'user-info'],
    queryFn: fetchUserInfo,
    enabled,
  });
}

export function useSendAuthCode() {
  return useMutation({
    mutationFn: (email: string) => sendAuthCode(email),
  });
}

export function useVerifyAuthCode() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ email, code }: { email: string; code: string }) => verifyAuthCode(email, code),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['auth'] });
    },
  });
}

export function useLogout() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: logoutAuth,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['auth'] });
    },
  });
}

export function useDeleteSavedCard() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (cardId: number) => deleteSavedCard(cardId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['auth', 'user-info'] });
    },
  });
}
