import { apiFetch } from './client';
import type { AuthSessionResponse, UserInfoResponse } from '../types/api';

export function fetchAuthSession(): Promise<AuthSessionResponse> {
  return apiFetch<AuthSessionResponse>('/api/auth/session');
}

export function sendAuthCode(email: string): Promise<{ status: string; message: string }> {
  return apiFetch('/api/auth/send-code', {
    method: 'POST',
    body: JSON.stringify({ email }),
  });
}

export function verifyAuthCode(
  email: string,
  code: string,
): Promise<{ status: string; message: string }> {
  return apiFetch('/api/auth/verify-code', {
    method: 'POST',
    body: JSON.stringify({ email, code }),
  });
}

export function logoutAuth(): Promise<{ status: string }> {
  return apiFetch('/api/auth/logout', { method: 'POST' });
}

export function fetchUserInfo(): Promise<UserInfoResponse> {
  return apiFetch<UserInfoResponse>('/api/user-info');
}

export function deleteSavedCard(cardId: number): Promise<{ status: string; id: number }> {
  return apiFetch(`/api/user/cards/${cardId}`, { method: 'DELETE' });
}
