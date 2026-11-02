/**
 * CampusFix Authentication Context Provider Component
 *
 * Implements:
 * - In-memory access token lifecycle management (never stored in localStorage)
 * - Automatic bootstrap silent session restoration on mount via HttpOnly cookie
 * - Session expiry listener synchronization with ApiClient
 * - Role profiles and deterministic authentication state
 */

import React, {
  useCallback,
  useEffect,
  useMemo,
  useState,
} from 'react';
import { authApi } from '../api/auth';
import { apiClient } from '../api/client';
import type {
  User,
  UserCreatePayload,
  UserLoginPayload,
} from '../types';
import { AuthContext, type AuthContextType } from './AuthContext';

export interface AuthProviderProps {
  children: React.ReactNode;
  /**
   * Optional flag to disable automatic bootstrap refresh on mount (useful in isolated tests).
   * Defaults to true.
   */
  autoBootstrap?: boolean;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({
  children,
  autoBootstrap = true,
}) => {
  const [user, setUser] = useState<User | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(autoBootstrap);

  // Synchronize in-memory token with ApiClient whenever state changes
  const updateToken = useCallback((token: string | null) => {
    setAccessToken(token);
    apiClient.setAccessToken(token);
  }, []);

  // Listen to ApiClient events (background session expiry or token rotation)
  useEffect(() => {
    const unsubscribeExpiry = apiClient.onSessionExpired(() => {
      setUser(null);
      setAccessToken(null);
    });

    const unsubscribeRefresh = apiClient.onTokenRefreshed((newToken) => {
      setAccessToken(newToken);
    });

    return () => {
      unsubscribeExpiry();
      unsubscribeRefresh();
    };
  }, []);

  const refreshSession = useCallback(async (): Promise<boolean> => {
    try {
      const tokenRes = await authApi.refresh();
      updateToken(tokenRes.access_token);
      const profile = await authApi.getMe();
      setUser(profile);
      return true;
    } catch {
      updateToken(null);
      setUser(null);
      return false;
    }
  }, [updateToken]);

  // Initial bootstrap: attempt silent session recovery from HttpOnly refresh cookie on application load
  useEffect(() => {
    if (!autoBootstrap) {
      setIsLoading(false);
      return;
    }

    let isMounted = true;

    const bootstrap = async () => {
      try {
        const success = await refreshSession();
        if (!success && isMounted) {
          updateToken(null);
          setUser(null);
        }
      } catch {
        if (isMounted) {
          updateToken(null);
          setUser(null);
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    };

    bootstrap();

    return () => {
      isMounted = false;
    };
  }, [autoBootstrap, refreshSession, updateToken]);

  const login = useCallback(
    async (credentials: UserLoginPayload): Promise<User> => {
      setIsLoading(true);
      try {
        const loginData = await authApi.login(credentials);
        updateToken(loginData.access_token);
        setUser(loginData.user);
        return loginData.user;
      } finally {
        setIsLoading(false);
      }
    },
    [updateToken]
  );

  const register = useCallback(
    async (data: UserCreatePayload): Promise<User> => {
      setIsLoading(true);
      try {
        const newUser = await authApi.register(data);
        return newUser;
      } finally {
        setIsLoading(false);
      }
    },
    []
  );

  const logout = useCallback(async (): Promise<void> => {
    setIsLoading(true);
    try {
      await authApi.logout();
    } catch (err) {
      console.warn('Logout request encountered an error, clearing client state anyway:', err);
    } finally {
      updateToken(null);
      setUser(null);
      setIsLoading(false);
    }
  }, [updateToken]);

  const value = useMemo<AuthContextType>(
    () => ({
      user,
      accessToken,
      isLoading,
      isAuthenticated: Boolean(user && accessToken),
      login,
      register,
      logout,
      refreshSession,
    }),
    [user, accessToken, isLoading, login, register, logout, refreshSession]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};
