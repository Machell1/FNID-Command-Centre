import api from './client';
import type { DashboardData, CommandDashboardData } from '../types/user';

export async function fetchDashboard(): Promise<DashboardData> {
  const res = await api.get('/dashboard/');
  return res.data;
}

export async function fetchCommandDashboard(): Promise<CommandDashboardData> {
  const res = await api.get('/dashboard/command');
  return res.data;
}

export async function fetchNotificationCount(): Promise<{ total: number; critical: number }> {
  const res = await api.get('/dashboard/notifications/count');
  return res.data;
}
