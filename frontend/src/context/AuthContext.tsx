/**
 * src/context/AuthContext.tsx
 * Authentication state: current account, JWT persistence, login/register/logout actions.
 * A 401 from any API call (expired/invalid token) logs the user out globally.
 */

import React, { createContext, useCallback, useContext, useEffect, useState } from 'react';
import {
  getMe,
  getToken,
  login as apiLogin,
  register as apiRegister,
  setToken,
  updateMe,
  changePassword as apiChangePassword,
  deleteAccount as apiDeleteAccount,
} from '../api/client';

export interface AuthUser {
  id: number;
  email: string;
  full_name: string;
  created_at: string;
  last_login_at?: string | null;
}

interface AuthContextType {
  user: AuthUser | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (fullName: string, email: string, password: string) => Promise<void>;
  logout: () => void;
  updateName: (fullName: string) => Promise<void>;
  changePassword: (currentPassword: string, newPassword: string) => Promise<void>;
  deleteAccount: (password: string) => Promise<void>;
}

const AuthContext = createContext<AuthContextType | null>(null);

// Keys written by older versions of the app, when data lived in the browser only.
const LEGACY_LOCAL_KEYS = [
  'fitbot_logged_meals',
  'fitbot_saved_routine',
  'fitbot_routine_split',
  'fitbot_routine_days_per_week',
];

function clearLegacyLocalData() {
  try {
    LEGACY_LOCAL_KEYS.forEach((k) => localStorage.removeItem(k));
  } catch {
    /* ignore */
  }
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(() => Boolean(getToken()));

  // Restore the session from a stored token on first load.
  useEffect(() => {
    if (!getToken()) return;
    let cancelled = false;
    getMe()
      .then((me: AuthUser) => {
        if (!cancelled) setUser(me);
      })
      .catch(() => {
        if (!cancelled) {
          setToken(null);
          setUser(null);
        }
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Any API call answered with 401 means the token is no longer valid.
  useEffect(() => {
    const onUnauthorized = () => setUser(null);
    window.addEventListener('fitbot:unauthorized', onUnauthorized);
    return () => window.removeEventListener('fitbot:unauthorized', onUnauthorized);
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const res = await apiLogin(email.trim(), password);
    clearLegacyLocalData();
    setToken(res.access_token);
    setUser(res.user);
  }, []);

  const register = useCallback(async (fullName: string, email: string, password: string) => {
    const res = await apiRegister(fullName.trim(), email.trim(), password);
    clearLegacyLocalData();
    setToken(res.access_token);
    setUser(res.user);
  }, []);

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
  }, []);

  const updateName = useCallback(async (fullName: string) => {
    const updated = await updateMe(fullName.trim());
    setUser(updated);
  }, []);

  const changePassword = useCallback(async (currentPassword: string, newPassword: string) => {
    await apiChangePassword(currentPassword, newPassword);
  }, []);

  const deleteAccount = useCallback(async (password: string) => {
    await apiDeleteAccount(password);
    setToken(null);
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: Boolean(user),
        isLoading,
        login,
        register,
        logout,
        updateName,
        changePassword,
        deleteAccount,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return ctx;
}
