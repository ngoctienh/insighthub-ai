import React, { createContext, useContext, useEffect, useState } from "react";
import { api } from "../api/client";
import { RoleCode, User } from "../types";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  login: (identifier: string, password: string) => Promise<User>;
  register: (payload: {
    username: string;
    email: string;
    full_name: string;
    password: string;
  }) => Promise<User>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
  hasRole: (...roles: RoleCode[]) => boolean;
  isInternal: boolean;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const refreshUser = async () => {
    const token = localStorage.getItem("insighthub_access_token");
    if (!token) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      const res = await api.get<User>("/auth/me/");
      setUser(res.data);
    } catch {
      localStorage.removeItem("insighthub_access_token");
      localStorage.removeItem("insighthub_refresh_token");
      setUser(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refreshUser();
  }, []);

  const login = async (identifier: string, password: string): Promise<User> => {
    const res = await api.post<{ access: string; refresh: string; user: User }>(
      "/auth/login/",
      { identifier, password }
    );
    localStorage.setItem("insighthub_access_token", res.data.access);
    localStorage.setItem("insighthub_refresh_token", res.data.refresh);
    setUser(res.data.user);
    return res.data.user;
  };

  const register = async (payload: {
    username: string;
    email: string;
    full_name: string;
    password: string;
  }): Promise<User> => {
    const res = await api.post<{ access: string; refresh: string; user: User }>(
      "/auth/register/",
      payload
    );
    localStorage.setItem("insighthub_access_token", res.data.access);
    localStorage.setItem("insighthub_refresh_token", res.data.refresh);
    setUser(res.data.user);
    return res.data.user;
  };

  const logout = async () => {
    const refresh = localStorage.getItem("insighthub_refresh_token");
    try {
      if (refresh) {
        await api.post("/auth/logout/", { refresh });
      }
    } catch {
      // Ignore network errors on logout cleanup
    } finally {
      localStorage.removeItem("insighthub_access_token");
      localStorage.removeItem("insighthub_refresh_token");
      setUser(null);
    }
  };

  const hasRole = (...roles: RoleCode[]) => {
    if (!user) return false;
    return roles.includes(user.role_code);
  };

  const isInternal = Boolean(user && user.role_code !== "CUSTOMER");

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        login,
        register,
        logout,
        refreshUser,
        hasRole,
        isInternal,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
