import api from './client';
import type { AuthResponse } from '../types/user';

export async function fetchCurrentUser(): Promise<AuthResponse> {
  const res = await api.get('/auth/me');
  return res.data;
}

export async function loginUser(badge_number: string, password: string): Promise<AuthResponse> {
  const res = await api.post('/auth/login', { badge_number, password });
  return res.data;
}

export async function logoutUser(): Promise<{ ok: boolean }> {
  const res = await api.post('/auth/logout');
  return res.data;
}

export async function registerUser(
  email: string, password: string, confirm_password: string
): Promise<AuthResponse> {
  const res = await api.post('/auth/register', { email, password, confirm_password });
  return res.data;
}

export async function changePassword(
  current_password: string, new_password: string, confirm_password: string
): Promise<AuthResponse> {
  const res = await api.post('/auth/change-password', { current_password, new_password, confirm_password });
  return res.data;
}
