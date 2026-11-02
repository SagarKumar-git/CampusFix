import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { authApi } from '../../src/api/auth';
import { apiClient } from '../../src/api/client';
import { useAuth } from '../../src/context/AuthContext';
import { AuthProvider } from '../../src/context/AuthProvider';
import type { LoginResponseData, User } from '../../src/types';

describe('AuthContext and useAuth', () => {
  const mockUser: User = {
    id: 'student-1',
    email: 'student@university.edu',
    full_name: 'Student Name',
    role: 'STUDENT',
    is_active: true,
    created_at: '2026-11-01T00:00:00Z',
  };

  beforeEach(() => {
    apiClient.setAccessToken(null);
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('throws an error when useAuth is consumed outside AuthProvider', () => {
    // Suppress console.error in React during error boundary throw
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});

    expect(() => renderHook(() => useAuth())).toThrow(
      'useAuth must be used within an AuthProvider'
    );

    consoleError.mockRestore();
  });

  it('performs silent bootstrap refresh on mount when autoBootstrap is enabled', async () => {
    vi.spyOn(authApi, 'refresh').mockResolvedValue({
      access_token: 'bootstrapped-token',
      token_type: 'bearer',
      expires_in: 900,
    });
    vi.spyOn(authApi, 'getMe').mockResolvedValue(mockUser);

    const { result } = renderHook(() => useAuth(), {
      wrapper: ({ children }) => <AuthProvider>{children}</AuthProvider>,
    });

    expect(result.current.isLoading).toBe(true);

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.isAuthenticated).toBe(true);
    expect(result.current.user).toEqual(mockUser);
    expect(result.current.accessToken).toBe('bootstrapped-token');
    expect(apiClient.getAccessToken()).toBe('bootstrapped-token');
  });

  it('sets unauthenticated state if bootstrap refresh fails on mount', async () => {
    vi.spyOn(authApi, 'refresh').mockRejectedValue(new Error('No refresh cookie'));

    const { result } = renderHook(() => useAuth(), {
      wrapper: ({ children }) => <AuthProvider>{children}</AuthProvider>,
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.isAuthenticated).toBe(false);
    expect(result.current.user).toBeNull();
    expect(result.current.accessToken).toBeNull();
  });

  it('handles login successfully updating in-memory token and user profile', async () => {
    const loginData: LoginResponseData = {
      access_token: 'new-login-token',
      token_type: 'bearer',
      expires_in: 900,
      user: mockUser,
    };

    vi.spyOn(authApi, 'login').mockResolvedValue(loginData);

    const { result } = renderHook(() => useAuth(), {
      wrapper: ({ children }) => <AuthProvider autoBootstrap={false}>{children}</AuthProvider>,
    });

    expect(result.current.isAuthenticated).toBe(false);

    await act(async () => {
      const user = await result.current.login({
        email: 'student@university.edu',
        password: 'Password123!',
      });
      expect(user).toEqual(mockUser);
    });

    expect(result.current.isAuthenticated).toBe(true);
    expect(result.current.user).toEqual(mockUser);
    expect(result.current.accessToken).toBe('new-login-token');
    expect(apiClient.getAccessToken()).toBe('new-login-token');
  });

  it('handles logout clearing state and in-memory token', async () => {
    vi.spyOn(authApi, 'login').mockResolvedValue({
      access_token: 'login-token',
      token_type: 'bearer',
      expires_in: 900,
      user: mockUser,
    });
    vi.spyOn(authApi, 'logout').mockResolvedValue({ message: 'Logged out.' });

    const { result } = renderHook(() => useAuth(), {
      wrapper: ({ children }) => <AuthProvider autoBootstrap={false}>{children}</AuthProvider>,
    });

    await act(async () => {
      await result.current.login({
        email: 'student@university.edu',
        password: 'Password123!',
      });
    });

    expect(result.current.isAuthenticated).toBe(true);

    await act(async () => {
      await result.current.logout();
    });

    expect(result.current.isAuthenticated).toBe(false);
    expect(result.current.user).toBeNull();
    expect(result.current.accessToken).toBeNull();
    expect(apiClient.getAccessToken()).toBeNull();
  });
});
