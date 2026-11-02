import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiClient, ApiError } from '../../src/api/client';
import type { ErrorEnvelope, SuccessEnvelope } from '../../src/types';

describe('ApiClient', () => {
  let client: ApiClient;
  const mockBaseUrl = 'http://localhost:8000/api/v1';

  beforeEach(() => {
    client = new ApiClient(mockBaseUrl);
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('initializes with expected base URL and null access token', () => {
    expect(client.getAccessToken()).toBeNull();
  });

  it('manages in-memory access token correctly', () => {
    client.setAccessToken('test-jwt-token');
    expect(client.getAccessToken()).toBe('test-jwt-token');
    client.setAccessToken(null);
    expect(client.getAccessToken()).toBeNull();
  });

  it('attaches Authorization header when access token is present', async () => {
    client.setAccessToken('access-token-123');

    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => ({ success: true, data: { result: 'ok' } }),
    });
    global.fetch = mockFetch;

    const data = await client.get<SuccessEnvelope<{ result: string }>>('/test');

    expect(data.data.result).toBe('ok');
    expect(mockFetch).toHaveBeenCalledTimes(1);
    const callArgs = mockFetch.mock.calls[0];
    expect(callArgs[0]).toBe('http://localhost:8000/api/v1/test');
    expect(callArgs[1].headers['Authorization']).toBe('Bearer access-token-123');
    expect(callArgs[1].credentials).toBe('include');
  });

  it('does not attach Authorization header when skipAuth is true', async () => {
    client.setAccessToken('access-token-123');

    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => ({ success: true, data: {} }),
    });
    global.fetch = mockFetch;

    await client.request('/public', { skipAuth: true });

    const callArgs = mockFetch.mock.calls[0];
    expect(callArgs[1].headers['Authorization']).toBeUndefined();
  });

  it('parses standardized ErrorEnvelope on HTTP errors', async () => {
    const errorPayload: ErrorEnvelope = {
      success: false,
      error: {
        code: 'RESOURCE_NOT_FOUND',
        message: 'Ticket not found.',
        details: null,
      },
      timestamp: '2026-11-01T12:00:00Z',
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => errorPayload,
    });

    await expect(client.get('/tickets/invalid-id')).rejects.toThrow('Ticket not found.');

    try {
      await client.get('/tickets/invalid-id');
    } catch (err) {
      expect(err).toBeInstanceOf(ApiError);
      const apiErr = err as ApiError;
      expect(apiErr.status).toBe(404);
      expect(apiErr.code).toBe('RESOURCE_NOT_FOUND');
      expect(apiErr.timestamp).toBe('2026-11-01T12:00:00Z');
    }
  });

  it('triggers single-flight refresh on 401 and replays request with new token', async () => {
    client.setAccessToken('expired-token');

    let requestCount = 0;
    const mockFetch = vi.fn().mockImplementation((url: string) => {
      requestCount++;

      // First call to /tickets -> returns 401
      if (url.endsWith('/tickets') && requestCount === 1) {
        return Promise.resolve({
          ok: false,
          status: 401,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => ({
            success: false,
            error: { code: 'UNAUTHORIZED', message: 'Token expired' },
          }),
        });
      }

      // Refresh call -> returns new access token
      if (url.endsWith('/auth/refresh')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => ({
            success: true,
            data: { access_token: 'fresh-rotated-token' },
          }),
        });
      }

      // Replayed call to /tickets -> returns 200
      if (url.endsWith('/tickets') && requestCount > 1) {
        return Promise.resolve({
          ok: true,
          status: 200,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => ({
            success: true,
            data: [{ id: '1', title: 'Test Ticket' }],
          }),
        });
      }

      return Promise.reject(new Error('Unexpected URL'));
    });

    global.fetch = mockFetch;

    const result = await client.get<SuccessEnvelope<Array<{ id: string }>>>('/tickets');

    expect(result.data).toHaveLength(1);
    expect(client.getAccessToken()).toBe('fresh-rotated-token');
    // Verify sequence: original call (401) -> refresh (200) -> replayed call (200)
    expect(mockFetch).toHaveBeenCalledTimes(3);
    expect(mockFetch.mock.calls[0][0]).toContain('/tickets');
    expect(mockFetch.mock.calls[1][0]).toContain('/auth/refresh');
    expect(mockFetch.mock.calls[2][0]).toContain('/tickets');
    expect(mockFetch.mock.calls[2][1].headers['Authorization']).toBe(
      'Bearer fresh-rotated-token'
    );
  });

  it('coalesces multiple concurrent 401 requests into exactly ONE refresh call', async () => {
    client.setAccessToken('expired-token');

    let refreshCallCount = 0;
    const mockFetch = vi.fn().mockImplementation((url: string, opts: RequestInit) => {
      if (url.endsWith('/auth/refresh')) {
        refreshCallCount++;
        return new Promise((resolve) => {
          setTimeout(() => {
            resolve({
              ok: true,
              status: 200,
              headers: new Headers({ 'content-type': 'application/json' }),
              json: async () => ({
                success: true,
                data: { access_token: 'coalesced-new-token' },
              }),
            });
          }, 20);
        });
      }

      const authHeader = (opts?.headers as Record<string, string>)?.[
        'Authorization'
      ];
      if (authHeader === 'Bearer coalesced-new-token') {
        return Promise.resolve({
          ok: true,
          status: 200,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => ({ success: true, data: 'success' }),
        });
      }

      // First time before refresh: returns 401
      return Promise.resolve({
        ok: false,
        status: 401,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => ({
          success: false,
          error: { code: 'UNAUTHORIZED', message: 'Expired' },
        }),
      });
    });

    global.fetch = mockFetch;

    // Fire 3 simultaneous API calls
    const [res1, res2, res3] = await Promise.all([
      client.get<SuccessEnvelope<string>>('/req1'),
      client.get<SuccessEnvelope<string>>('/req2'),
      client.get<SuccessEnvelope<string>>('/req3'),
    ]);

    expect(res1.data).toBe('success');
    expect(res2.data).toBe('success');
    expect(res3.data).toBe('success');
    // Crucial invariant: exactly ONE call to /auth/refresh
    expect(refreshCallCount).toBe(1);
    expect(client.getAccessToken()).toBe('coalesced-new-token');
  });

  it('notifies onSessionExpired listeners and clears token if refresh fails', async () => {
    client.setAccessToken('stale-token');
    const sessionExpiredSpy = vi.fn();
    client.onSessionExpired(sessionExpiredSpy);

    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.endsWith('/auth/refresh')) {
        return Promise.resolve({
          ok: false,
          status: 401,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => ({
            success: false,
            error: { code: 'TOKEN_EXPIRED', message: 'Refresh token expired' },
          }),
        });
      }

      return Promise.resolve({
        ok: false,
        status: 401,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => ({
          success: false,
          error: { code: 'UNAUTHORIZED', message: 'Expired' },
        }),
      });
    });

    await expect(client.get('/protected')).rejects.toThrow();

    expect(sessionExpiredSpy).toHaveBeenCalledTimes(1);
    expect(client.getAccessToken()).toBeNull();
  });
});
