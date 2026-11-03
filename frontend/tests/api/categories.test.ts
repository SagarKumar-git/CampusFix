/**
 * Categories API Client Unit Tests
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { categoriesApi } from '../../src/api/categories';
import { apiClient } from '../../src/api/client';
import type { Category } from '../../src/types';

describe('categoriesApi Service', () => {
  beforeEach(() => {
    apiClient.setAccessToken('mock-admin-token');
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  const mockCategories: Category[] = [
    {
      id: 'cat-1',
      name: 'Classroom Audio-Visual',
      description: 'Projectors, microphones, and podium cables.',
      is_active: true,
      created_at: '2026-10-20T10:00:00Z',
    },
    {
      id: 'cat-2',
      name: 'Plumbing & Sanitary',
      description: 'Restroom sinks, pipes, and drains.',
      is_active: false,
      created_at: '2026-10-21T11:00:00Z',
    },
  ];

  it('listCategories defaults to active categories without query string', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => ({ success: true, data: [mockCategories[0]] }),
    });

    const result = await categoriesApi.listCategories();
    expect(result).toHaveLength(1);
    expect(result[0].name).toBe('Classroom Audio-Visual');
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringMatching(/\/categories$/),
      expect.objectContaining({ method: 'GET' })
    );
  });

  it('listCategories passes include_inactive=true query parameter when requested', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => ({ success: true, data: mockCategories }),
    });

    const result = await categoriesApi.listCategories(true);
    expect(result).toHaveLength(2);
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/categories?include_inactive=true'),
      expect.objectContaining({ method: 'GET' })
    );
  });

  it('getCategory fetches single category by UUID', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => ({ success: true, data: mockCategories[0] }),
    });

    const result = await categoriesApi.getCategory('cat-1');
    expect(result.id).toBe('cat-1');
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/categories/cat-1'),
      expect.objectContaining({ method: 'GET' })
    );
  });

  it('createCategory dispatches POST /categories with payload and returns created record', async () => {
    const newCategory: Category = {
      id: 'cat-3',
      name: 'HVAC & Climate Control',
      description: 'Thermostats, AC units, and heating ducts.',
      is_active: true,
      created_at: '2026-11-02T12:00:00Z',
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => ({ success: true, data: newCategory }),
    });

    const result = await categoriesApi.createCategory({
      name: 'HVAC & Climate Control',
      description: 'Thermostats, AC units, and heating ducts.',
      is_active: true,
    });

    expect(result.id).toBe('cat-3');
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringMatching(/\/categories$/),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          name: 'HVAC & Climate Control',
          description: 'Thermostats, AC units, and heating ducts.',
          is_active: true,
        }),
      })
    );
  });

  it('updateCategory dispatches PATCH /categories/{id} with partial payload', async () => {
    const updatedCategory: Category = {
      ...mockCategories[1],
      is_active: true,
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => ({ success: true, data: updatedCategory }),
    });

    const result = await categoriesApi.updateCategory('cat-2', { is_active: true });

    expect(result.is_active).toBe(true);
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/categories/cat-2'),
      expect.objectContaining({
        method: 'PATCH',
        body: JSON.stringify({ is_active: true }),
      })
    );
  });
});
