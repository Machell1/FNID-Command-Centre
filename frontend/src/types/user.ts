export interface UserProfile {
  badge_number: string;
  full_name: string;
  rank: string;
  section: string;
  role: string;
  unit_access: string | null;
  admin_tier: number | null;
  permissions: Record<string, Record<string, boolean>>;
}

export interface AuthResponse {
  ok: boolean;
  error?: string;
  user?: UserProfile;
  redirect?: string;
  message?: string;
  authenticated?: boolean;
}

export interface DashboardData {
  stats: {
    cases: number;
    intel: number;
    operations: number;
    firearms: number;
    narcotics: number;
    arrests: number;
  };
  recent_activity: Array<{
    table: string;
    action: string;
    badge: string;
    name: string;
    details: string;
    time: string;
  }>;
  alerts: Array<{
    id: number;
    type: string;
    severity: string;
    title: string;
    message: string;
    time: string;
  }>;
  portals: Record<string, {
    name: string;
    icon: string;
    color: string;
    description: string;
  }>;
  user: {
    badge_number: string;
    full_name: string;
    rank: string;
    role: string;
  };
}

export interface CommandDashboardData {
  monthly_cases: Array<{ month: string; count: number }>;
  seizure_types: { firearms: number; narcotics: number };
  case_status: Array<{ status: string; count: number }>;
}
