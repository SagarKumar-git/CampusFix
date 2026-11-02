/**
 * CampusFix Typed REST API Client
 *
 * Implements:
 * - Strict in-memory access token storage
 * - Automatic HttpOnly refresh cookie transmission (`credentials: 'include'`)
 * - Single-flight refresh mutex/promise queue preventing token reuse revocation
 * - Standardized CampusFix success/error envelope decoding and error throwing
 */

import type { ErrorEnvelope, SuccessEnvelope, ValidationErrorItem } from '../types';

export interface RequestOptions extends RequestInit {
  skipAuth?: boolean;
  isRetry?: boolean;
}

export class ApiError extends Error {
  public readonly status: number;
  public readonly code: string;
  public readonly details: ValidationErrorItem[] | Record<string, unknown> | null;
  public readonly timestamp?: string;

  constructor(
    status: number,
    code: string,
    message: string,
    details: ValidationErrorItem[] | Record<string, unknown> | null = null,
    timestamp?: string
  ) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.details = details;
    this.timestamp = timestamp;
  }
}

export class ApiClient {
  private baseUrl: string;
  private accessToken: string | null = null;
  private refreshPromise: Promise<string> | null = null;
  private sessionExpiredListeners: Array<() => void> = [];
  private tokenRefreshedListeners: Array<(newToken: string) => void> = [];

  constructor(baseUrl?: string) {
    const envBaseUrl = typeof import.meta !== 'undefined' && import.meta.env
      ? import.meta.env.VITE_API_BASE_URL
      : undefined;

    this.baseUrl = baseUrl || envBaseUrl || 'http://localhost:8000/api/v1';
    // Strip trailing slash if present
    if (this.baseUrl.endsWith('/')) {
      this.baseUrl = this.baseUrl.slice(0, -1);
    }
  }

  public setAccessToken(token: string | null): void {
    this.accessToken = token;
  }

  public getAccessToken(): string | null {
    return this.accessToken;
  }

  public onSessionExpired(callback: () => void): () => void {
    this.sessionExpiredListeners.push(callback);
    return () => {
      this.sessionExpiredListeners = this.sessionExpiredListeners.filter(
        (cb) => cb !== callback
      );
    };
  }

  public onTokenRefreshed(callback: (token: string) => void): () => void {
    this.tokenRefreshedListeners.push(callback);
    return () => {
      this.tokenRefreshedListeners = this.tokenRefreshedListeners.filter(
        (cb) => cb !== callback
      );
    };
  }

  private notifySessionExpired(): void {
    this.sessionExpiredListeners.forEach((cb) => {
      try {
        cb();
      } catch (err) {
        console.error('Error in onSessionExpired listener:', err);
      }
    });
  }

  private notifyTokenRefreshed(token: string): void {
    this.tokenRefreshedListeners.forEach((cb) => {
      try {
        cb(token);
      } catch (err) {
        console.error('Error in onTokenRefreshed listener:', err);
      }
    });
  }

  /**
   * Executes silent refresh under a single-flight promise.
   * If multiple requests encounter 401 simultaneously, only ONE network call
   * is made to /auth/refresh while all other calls await that same promise.
   */
  public async refreshAccessToken(): Promise<string> {
    if (this.refreshPromise) {
      return this.refreshPromise;
    }

    this.refreshPromise = (async () => {
      try {
        const url = `${this.baseUrl}/auth/refresh`;
        const res = await fetch(url, {
          method: 'POST',
          credentials: 'include',
          headers: {
            'Content-Type': 'application/json',
          },
        });

        if (!res.ok) {
          this.setAccessToken(null);
          this.notifySessionExpired();

          let errorEnvelope: ErrorEnvelope | null = null;
          try {
            errorEnvelope = (await res.json()) as ErrorEnvelope;
          } catch {
            // Ignore json parse error on non-json error responses
          }

          if (errorEnvelope?.error) {
            throw new ApiError(
              res.status,
              errorEnvelope.error.code,
              errorEnvelope.error.message,
              errorEnvelope.error.details,
              errorEnvelope.timestamp
            );
          }

          throw new ApiError(res.status, 'REFRESH_FAILED', 'Failed to refresh session.');
        }

        const data = (await res.json()) as SuccessEnvelope<{ access_token: string }>;
        const newToken = data.data.access_token;
        this.setAccessToken(newToken);
        this.notifyTokenRefreshed(newToken);
        return newToken;
      } finally {
        this.refreshPromise = null;
      }
    })();

    return this.refreshPromise;
  }

  public async request<T>(
    path: string,
    options: RequestOptions = {}
  ): Promise<T> {
    const normalizedPath = path.startsWith('/') ? path : `/${path}`;
    const url = `${this.baseUrl}${normalizedPath}`;

    const headers: Record<string, string> = {
      ...(options.headers as Record<string, string> | undefined),
    };

    if (!(options.body instanceof FormData) && !headers['Content-Type']) {
      headers['Content-Type'] = 'application/json';
    }

    if (!options.skipAuth && this.accessToken) {
      headers['Authorization'] = `Bearer ${this.accessToken}`;
    }

    const fetchOptions: RequestInit = {
      ...options,
      headers,
      credentials: 'include', // Ensure HttpOnly cookies are attached across requests
    };

    const res = await fetch(url, fetchOptions);

    // Check for HTTP 401 on authenticated requests (and avoid refreshing during auth handshakes)
    const isAuthRoute =
      normalizedPath.startsWith('/auth/login') ||
      normalizedPath.startsWith('/auth/register') ||
      normalizedPath.startsWith('/auth/refresh');

    if (res.status === 401 && !options.skipAuth && !isAuthRoute && !options.isRetry) {
      const newToken = await this.refreshAccessToken();
      // Retry the original request with the new access token
      return await this.request<T>(path, {
        ...options,
        isRetry: true,
        headers: {
          ...headers,
          Authorization: `Bearer ${newToken}`,
        },
      });
    }

    // Process normal response
    let responseData: unknown = null;
    const contentType = res.headers.get('content-type');
    if (contentType && contentType.includes('application/json')) {
      try {
        responseData = await res.json();
      } catch {
        // Fallback for body read failure
      }
    }

    if (!res.ok) {
      const errorEnvelope = responseData as ErrorEnvelope | null;
      if (errorEnvelope?.error) {
        throw new ApiError(
          res.status,
          errorEnvelope.error.code,
          errorEnvelope.error.message,
          errorEnvelope.error.details,
          errorEnvelope.timestamp
        );
      }

      throw new ApiError(
        res.status,
        `HTTP_${res.status}`,
        res.statusText || 'Request failed'
      );
    }

    return responseData as T;
  }

  public get<T>(path: string, options?: RequestOptions): Promise<T> {
    return this.request<T>(path, { ...options, method: 'GET' });
  }

  public post<T>(path: string, body?: unknown, options?: RequestOptions): Promise<T> {
    return this.request<T>(path, {
      ...options,
      method: 'POST',
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  }

  public patch<T>(path: string, body?: unknown, options?: RequestOptions): Promise<T> {
    return this.request<T>(path, {
      ...options,
      method: 'PATCH',
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  }

  public delete<T>(path: string, options?: RequestOptions): Promise<T> {
    return this.request<T>(path, { ...options, method: 'DELETE' });
  }
}

// Global singleton instance for application use
export const apiClient = new ApiClient();
