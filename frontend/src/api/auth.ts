/**
 * CampusFix Authentication API Service
 *
 * Implements /api/v1/auth operations:
 * - register (public, creates STUDENT role)
 * - login (public, stores access JWT in memory, sets HttpOnly refresh cookie)
 * - refresh (silent token rotation under single-flight mutex)
 * - logout (revokes session family and clears cookie)
 * - getMe (fetches current user profile)
 */

import { apiClient } from './client';
import type {
  LoginResponseData,
  MessageResponse,
  SuccessEnvelope,
  TokenResponse,
  User,
  UserCreatePayload,
  UserLoginPayload,
} from '../types';

export const authApi = {
  /**
   * Registers a new student account. Strictly assigns STUDENT role.
   */
  async register(data: UserCreatePayload): Promise<User> {
    const res = await apiClient.post<SuccessEnvelope<User>>('/auth/register', data, {
      skipAuth: true,
    });
    return res.data;
  },

  /**
   * Authenticates user credentials.
   * On success: stores access token in client memory and receives HttpOnly refresh cookie.
   */
  async login(credentials: UserLoginPayload): Promise<LoginResponseData> {
    const res = await apiClient.post<SuccessEnvelope<LoginResponseData>>(
      '/auth/login',
      credentials,
      { skipAuth: true }
    );
    apiClient.setAccessToken(res.data.access_token);
    return res.data;
  },

  /**
   * Atomically rotates single-use refresh token via single-flight mutex.
   */
  async refresh(): Promise<TokenResponse> {
    const accessToken = await apiClient.refreshAccessToken();
    return {
      access_token: accessToken,
      token_type: 'bearer',
      expires_in: 900,
    };
  },

  /**
   * Terminates active session family and clears refresh cookie.
   */
  async logout(): Promise<MessageResponse> {
    try {
      const res = await apiClient.post<SuccessEnvelope<MessageResponse>>('/auth/logout');
      return res.data;
    } finally {
      apiClient.setAccessToken(null);
    }
  },

  /**
   * Retrieves authenticated profile of current user.
   */
  async getMe(): Promise<User> {
    const res = await apiClient.get<SuccessEnvelope<User>>('/auth/me');
    return res.data;
  },
};
