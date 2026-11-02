import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import App from '../src/App';
import { apiClient } from '../src/api/client';

describe('CampusFix Application Shell & Routing', () => {
  beforeEach(() => {
    apiClient.setAccessToken(null);
    vi.restoreAllMocks();
    // Default mock fetch for bootstrap refresh -> fails (not logged in)
    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/auth/refresh')) {
        return Promise.resolve({
          ok: false,
          status: 401,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => ({ success: false, error: { code: 'UNAUTHORIZED' } }),
        });
      }
      return Promise.reject(new Error(`Unexpected fetch to ${url}`));
    });
  });

  it('renders application landing and redirects unauthenticated visitor to login', async () => {
    render(<App />);

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: /sign in to campusfix/i })
      ).toBeInTheDocument();
    });

    expect(screen.getByLabelText(/institutional email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument();
  });
});
