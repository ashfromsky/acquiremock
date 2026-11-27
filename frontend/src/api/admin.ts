import { apiFetch } from './client';
import type { AdminSessionResponse } from '../types/api';

export function fetchAdminSession(): Promise<AdminSessionResponse> {
  return apiFetch<AdminSessionResponse>('/api/admin/session');
}

export function loginAdmin(username: string, password: string): Promise<AdminSessionResponse> {
  return apiFetch<AdminSessionResponse>('/api/admin/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  });
}

export function logoutAdmin(): Promise<{ status: string }> {
  return apiFetch<{ status: string }>('/api/admin/logout', {
    method: 'POST',
  });
}
