import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { authApi } from '../../src/api/auth';
import { apiClient } from '../../src/api/client';
import type { LoginResponseData, User } from '../../src/types';

describe('authApi Service', () => {
  beforeEach(() => {
    apiClient.setAccessToken(null);
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('register dispatches POST /auth/register and returns user', async () => {
    const mockUser: User = {
      id: 'user-uuid-1',
      email: 'student@university.edu',
      full_name: 'Alex Student',
      role: 'STUDENT',
      is_active: true,
      created_at: '2026-11-01T10:00:00Z',
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => ({ success: true, data: mockUser }),
    });

    const user = await authApi.register({
      full_name: 'Alex Student',
      email: 'student@university.edu',
      password: 'Password123!',
    });

    expect(user).toEqual(mockUser);
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/auth/register'),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          full_name: 'Alex Student',
          email: 'student@university.edu',
          password: 'Password123!',
        }),
      })
    );
  });

  it('login dispatches POST /auth/login, sets in-memory token, and returns payload', async () => {
    const mockLoginData: LoginResponseData = {
      access_token: 'login-jwt-token',
      token_type: 'bearer',
      expires_in: 900,
      user: {
        id: 'user-uuid-1',
        email: 'student@university.edu',
        full_name: 'Alex Student',
        role: 'STUDENT',
        is_active: true,
        created_at: '2026-11-01T10:00:00Z',
      },
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => ({ success: true, data: mockLoginData }),
    });

    const data = await authApi.login({
      email: 'student@university.edu',
      password: 'Password123!',
    });

    expect(data.access_token).toBe('login-jwt-token');
    expect(data.user.role).toBe('STUDENT');
    expect(apiClient.getAccessToken()).toBe('login-jwt-token');
  });

  it('logout dispatches POST /auth/logout and clears in-memory token', async () => {
    apiClient.setAccessToken('active-token');

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => ({ success: true, data: { message: 'Logged out.' } }),
    });

    await authApi.logout();

    expect(apiClient.getAccessToken()).toBeNull();
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/auth/logout'),
      expect.objectContaining({ method: 'POST' })
    );
  });

  it('getMe retrieves authenticated user profile', async () => {
    apiClient.setAccessToken('active-token');

    const mockProfile: User = {
      id: 'staff-uuid-1',
      email: 'tech@university.edu',
      full_name: 'Jordan Tech',
      role: 'STAFF',
      is_active: true,
      created_at: '2026-10-15T08:00:00Z',
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => ({ success: true, data: mockProfile }),
    });

    const profile = await authApi.getMe();
    expect(profile.role).toBe('STAFF');
    expect(profile.email).toBe('tech@university.edu');
  });
});
