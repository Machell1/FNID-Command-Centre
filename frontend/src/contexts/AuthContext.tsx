import { createContext, useCallback, useEffect, useState, type ReactNode } from 'react';
import type { UserProfile } from '../types/user';
import { fetchCurrentUser, loginUser, logoutUser } from '../api/auth';

interface AuthContextType {
  user: UserProfile | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
  login: (badge: string, password: string) => Promise<{ ok: boolean; redirect?: string; error?: string }>;
  logout: () => Promise<void>;
  can: (resource: string, action: string) => boolean;
  clearError: () => void;
}

export const AuthContext = createContext<AuthContextType>({
  user: null,
  isAuthenticated: false,
  isLoading: true,
  error: null,
  login: async () => ({ ok: false }),
  logout: async () => {},
  can: () => false,
  clearError: () => {},
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const checkAuth = useCallback(async () => {
    try {
      const data = await fetchCurrentUser();
      if (data.authenticated) {
        const { authenticated: _, ...profile } = data as any;
        setUser(profile as UserProfile);
      } else {
        setUser(null);
      }
    } catch {
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  const login = useCallback(async (badge: string, password: string) => {
    setError(null);
    try {
      const data = await loginUser(badge, password);
      if (data.ok && data.user) {
        setUser(data.user);
        return { ok: true, redirect: data.redirect };
      }
      const msg = data.error || 'Login failed.';
      setError(msg);
      return { ok: false, error: msg };
    } catch (err: any) {
      const msg = err.response?.data?.error || 'Login failed. Please try again.';
      setError(msg);
      return { ok: false, error: msg };
    }
  }, []);

  const logout = useCallback(async () => {
    try {
      await logoutUser();
    } catch {
      // Logout even if request fails
    }
    setUser(null);
  }, []);

  const can = useCallback((resource: string, action: string) => {
    if (!user) return false;
    if (user.role === 'admin') return true;
    return !!user.permissions?.[resource]?.[action];
  }, [user]);

  const clearError = useCallback(() => setError(null), []);

  return (
    <AuthContext.Provider value={{
      user,
      isAuthenticated: !!user,
      isLoading,
      error,
      login,
      logout,
      can,
      clearError,
    }}>
      {children}
    </AuthContext.Provider>
  );
}
